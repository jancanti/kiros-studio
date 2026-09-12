"""Fila persistente em SQLite para execução de campanhas, storyboard e pipelines (M05)."""
from datetime import datetime, timezone
import hashlib
import json
import logging
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid

from kiros.campaigns.models import UnapprovedExecutionError
from kiros.core.contracts import Provenance
from kiros.cost import CostManager
from kiros.execution.diagnostics import analyze_execution_failure
from kiros.execution.models import (
    CancellationImpact,
    ExecutionJob,
    ExecutionVersion,
    FailureDiagnostic,
    JobExecutionError,
    QueueError,
    RateLimitExceededError,
    VALID_JOB_STATUSES,
    VALID_MONITORING_MODES,
)
from kiros.infrastructure.local import SQLiteDatabase

logger = logging.getLogger(__name__)


class ExecutionQueue:
    """Gerenciador da fila persistente com concorrência, prioridade, rate limit, timeout e idempotência."""

    def __init__(
        self,
        db: SQLiteDatabase,
        cost_manager: CostManager,
        fidelity_service: Optional[Any] = None,
        memory_store: Optional[Any] = None,
    ):
        self.db = db
        self.cost_manager = cost_manager
        self.fidelity_service = fidelity_service
        self.memory_store = memory_store
        # Registro em memória de timestamps de requisições por provider para rate limiting
        self._provider_call_timestamps: Dict[str, List[float]] = {}
        # Configuração de taxa máxima de requisições por minuto por provider
        self.rate_limits_rpm: Dict[str, int] = {
            'gemini': 60,
            'openai': 50,
            'firefly': 40,
            'custom': 100,
        }

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def set_monitoring_mode(self, campaign_id: str, mode: str) -> None:
        clean_mode = str(mode).strip().lower()
        if clean_mode not in VALID_MONITORING_MODES:
            raise ValueError(f"Modo de monitoramento inválido: '{clean_mode}'. Use {VALID_MONITORING_MODES}")
        with sqlite3.connect(self.db.path) as conn:
            conn.execute('UPDATE campaigns SET monitoring_mode=?, updated_at=? WHERE id=?',
                         (clean_mode, self._now(), campaign_id))

    def get_monitoring_mode(self, campaign_id: str) -> str:
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT monitoring_mode FROM campaigns WHERE id=?', (campaign_id,)).fetchone()
            if row and row['monitoring_mode']:
                return row['monitoring_mode']
        return 'supervised'

    def check_rate_limit(self, provider_id: str) -> bool:
        """Verifica se o rate limit para o provedor não foi ultrapassado na janela de 60 segundos."""
        now = time.time()
        prov = provider_id.lower().strip()
        rpm = self.rate_limits_rpm.get(prov, 60)

        history = self._provider_call_timestamps.setdefault(prov, [])
        # Filtra timestamps anteriores a 60s
        self._provider_call_timestamps[prov] = [t for t in history if now - t < 60.0]
        return len(self._provider_call_timestamps[prov]) < rpm

    def record_provider_call(self, provider_id: str) -> None:
        """Registra uma chamada realizada ao provedor para controle de rate limit."""
        prov = provider_id.lower().strip()
        history = self._provider_call_timestamps.setdefault(prov, [])
        history.append(time.time())

    def enqueue_campaign_execution(
        self,
        campaign_id: str,
        priority: int = 10,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
    ) -> List[ExecutionJob]:
        """Enfileira todas as etapas do pipeline de uma campanha aprovada com idempotência estrita (M05-A01, M05-A03)."""
        now = self._now()
        created_jobs: List[ExecutionJob] = []

        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.row_factory = sqlite3.Row
            camp = conn.execute('SELECT * FROM campaigns WHERE id=?', (campaign_id,)).fetchone()
            if not camp:
                raise ValueError(f"Campanha '{campaign_id}' não encontrada.")

            current_plan_version = int(camp['plan_version'])
            if camp['status'] not in ('approved', 'queued', 'running', 'paused') or camp['approved_version'] != current_plan_version:
                raise UnapprovedExecutionError(
                    f"Execução recusada: Campanha '{campaign_id}' não possui aprovação válida para a versão atual do plano (v{current_plan_version})."
                )

            step_rows = [dict(r) for r in conn.execute(
                'SELECT * FROM pipeline_steps WHERE campaign_id=? ORDER BY step_order ASC',
                (campaign_id,),
            ).fetchall()]
            if not step_rows:
                raise ValueError(f"Campanha '{campaign_id}' não possui etapas no pipeline.")

            slide_rows = {
                r['id']: dict(r)
                for r in conn.execute('SELECT * FROM storyboard_slides WHERE campaign_id=?', (campaign_id,)).fetchall()
            }

            existing_rows = {
                r['idempotency_key']: self._row_to_job(r)
                for r in conn.execute('SELECT * FROM execution_jobs WHERE campaign_id=?', (campaign_id,)).fetchall()
            }
            mode = camp['monitoring_mode'] or 'supervised'

        initial_job_status = 'paused' if mode == 'manual' else 'pending'
        jobs_to_insert = []

        for step in step_rows:
            step_id = step['id']
            slide_id = step['slide_id']
            slide = slide_rows.get(slide_id, {})
            prompt = slide.get('visual_prompt', step['name'])
            provider_id = step['provider_id']
            model_id = step['model_id']
            estimated_cost = float(step['estimated_cost'])

            idempotency_key = f"{campaign_id}:{step_id}:v{current_plan_version}"

            if idempotency_key in existing_rows:
                created_jobs.append(existing_rows[idempotency_key])
                continue

            # Reserva de orçamento com CostManager fora de transação na fila
            res_id = self.cost_manager.reserve_budget(
                campaign_id=campaign_id,
                estimated_cost=estimated_cost,
                approved=True,
            )

            job_id = uuid.uuid4().hex
            jobs_to_insert.append({
                'id': job_id,
                'values': (
                    job_id, campaign_id, slide_id, step_id, idempotency_key,
                    initial_job_status, priority, max_retries, timeout_seconds,
                    provider_id, model_id, prompt, step['params_json'],
                    estimated_cost, res_id, now, now,
                ),
            })

        if jobs_to_insert:
            with sqlite3.connect(self.db.path, timeout=30.0) as conn:
                conn.row_factory = sqlite3.Row
                conn.execute('BEGIN IMMEDIATE')
                for item in jobs_to_insert:
                    conn.execute(
                        '''INSERT INTO execution_jobs (
                            id, campaign_id, slide_id, step_id, idempotency_key, status,
                            priority, attempt, max_retries, timeout_seconds, provider_id,
                            model_id, prompt, params_json, estimated_cost, actual_cost,
                            budget_reservation_id, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, 0.0, ?, ?, ?)''',
                        item['values'],
                    )
                    job_row = conn.execute('SELECT * FROM execution_jobs WHERE id=?', (item['id'],)).fetchone()
                    created_jobs.append(self._row_to_job(job_row))

                camp_status = 'paused' if mode == 'manual' else 'queued'
                conn.execute('UPDATE campaigns SET status=?, updated_at=? WHERE id=?', (camp_status, now, campaign_id))

        return created_jobs

    def claim_next_job(self, worker_id: str) -> Optional[ExecutionJob]:
        """Reivindica atomicamente o próximo trabalho 'pending' considerando prioridade e rate limits (M05-A01)."""
        now = self._now()
        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')

            # Recupera candidatos ordenados por prioridade (menor número = maior urgência) e data de criação
            candidates = conn.execute(
                '''SELECT * FROM execution_jobs
                   WHERE status = 'pending' AND locked_by IS NULL
                   ORDER BY priority ASC, created_at ASC''',
            ).fetchall()

            for job_row in candidates:
                prov = job_row['provider_id']
                if not self.check_rate_limit(prov):
                    # Provedor em rate limit: pula este e tenta o próximo candidato
                    continue

                job_id = job_row['id']
                attempt = int(job_row['attempt']) + 1

                conn.execute(
                    '''UPDATE execution_jobs
                       SET status='running', locked_by=?, locked_at=?, started_at=?, attempt=?, updated_at=?
                       WHERE id=? AND status='pending' AND locked_by IS NULL''',
                    (worker_id, now, now, attempt, now, job_id),
                )

                # Confirma se o lock foi concedido a este worker
                claimed = conn.execute('SELECT * FROM execution_jobs WHERE id=?', (job_id,)).fetchone()
                if claimed and claimed['locked_by'] == worker_id:
                    # Registra a chamada para o rate limiter
                    self.record_provider_call(prov)
                    # Atualiza campanha para 'running' se estava 'queued'
                    conn.execute(
                        "UPDATE campaigns SET status='running', updated_at=? WHERE id=? AND status IN ('queued', 'approved')",
                        (now, claimed['campaign_id']),
                    )
                    return self._row_to_job(claimed)

        return None

    def release_stale_locks(self, timeout_multiplier: float = 2.0) -> int:
        """Recupera trabalhos cujo worker travou ou reiniciou, liberando o lock e restaurando status (M05-A05)."""
        now_dt = datetime.now(timezone.utc)
        recovered = 0

        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')

            running_jobs = conn.execute(
                "SELECT * FROM execution_jobs WHERE status='running' AND locked_by IS NOT NULL"
            ).fetchall()

            for job in running_jobs:
                timeout_limit = float(job['timeout_seconds']) * timeout_multiplier
                locked_str = job['locked_at'] or job['started_at'] or job['created_at']
                try:
                    locked_dt = datetime.fromisoformat(locked_str)
                    elapsed = (now_dt - locked_dt).total_seconds()
                except Exception:
                    elapsed = timeout_limit + 1.0

                if elapsed > timeout_limit:
                    job_id = job['id']
                    attempt = int(job['attempt'])
                    max_ret = int(job['max_retries'])

                    if attempt >= max_ret:
                        # Excedeu retries mesmo em recuperação de crash
                        diag = analyze_execution_failure(
                            job['provider_id'],
                            f"Recuperação de crash na etapa {job['step_id']}",
                            "Worker encerrou inesperadamente e atingiu limite de tentativas.",
                            float(job['estimated_cost']),
                        )
                        conn.execute(
                            '''UPDATE execution_jobs
                               SET status='failed', locked_by=NULL, locked_at=NULL,
                                   error_provider=?, error_step=?, error_probable_cause=?,
                                   error_suggested_fix=?, error_potential_cost=?, updated_at=?
                               WHERE id=?''',
                            (diag.provider, diag.step, diag.probable_cause, diag.suggested_fix, diag.potential_cost, self._now(), job_id),
                        )
                    else:
                        # Devolve para a fila em 'pending'
                        conn.execute(
                            "UPDATE execution_jobs SET status='pending', locked_by=NULL, locked_at=NULL, updated_at=? WHERE id=?",
                            (self._now(), job_id),
                        )
                    recovered += 1

        return recovered

    def record_job_success(
        self,
        job_id: str,
        output_asset_id: str,
        actual_cost: float,
        output_data: Optional[Dict[str, Any]] = None,
    ) -> ExecutionJob:
        """Registra conclusão de etapa com sucesso, preserva versão e consolida reserva no CostManager (M05-A01, M05-A02)."""
        now = self._now()
        out_json = json.dumps(output_data or {}, ensure_ascii=False)

        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.row_factory = sqlite3.Row
            job = conn.execute('SELECT * FROM execution_jobs WHERE id=?', (job_id,)).fetchone()
            if not job:
                raise ValueError(f"Trabalho '{job_id}' não encontrado.")
            job_dict = dict(job)

        campaign_id = job_dict['campaign_id']
        slide_id = job_dict['slide_id']
        step_id = job_dict['step_id']
        res_id = job_dict['budget_reservation_id']

        # Efetiva reserva no CostManager fora do lock
        if res_id:
            try:
                self.cost_manager.commit_reservation(
                    reservation_id=res_id,
                    actual_cost=actual_cost,
                    stages=[job_dict['provider_id']],
                    asset_id=output_asset_id,
                )
            except Exception:
                pass

        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')

            conn.execute(
                '''UPDATE execution_jobs
                   SET status='completed', actual_cost=?, output_asset_id=?,
                       output_data_json=?, locked_by=NULL, locked_at=NULL,
                       completed_at=?, updated_at=?
                   WHERE id=?''',
                (float(actual_cost), output_asset_id, out_json, now, now, job_id),
            )

            conn.execute(
                "UPDATE pipeline_steps SET status='completed', updated_at=? WHERE id=?",
                (now, step_id),
            )

            # Preserva versão de geração (Seção 52, 53 e M06-A03: Nunca apagar versões)
            ver_id = None
            if slide_id:
                ver_count_row = conn.execute(
                    'SELECT COALESCE(MAX(version_number), 0) + 1 FROM execution_versions WHERE slide_id=?',
                    (slide_id,),
                ).fetchone()
                ver_num = int(ver_count_row[0])

                # Marca versões anteriores como não-atuais
                conn.execute('UPDATE execution_versions SET is_current=0 WHERE slide_id=?', (slide_id,))

                prompt_str = job_dict['prompt'] or ''
                prompt_ref = hashlib.sha256(prompt_str.encode('utf-8')).hexdigest()[:16]

                params_data = json.loads(job_dict['params_json'] or '{}')
                reason = params_data.get('reason', 'Geração inicial' if ver_num == 1 else 'Regeneração localizada')
                requester = params_data.get('requester', 'system')
                parent_version_id = params_data.get('parent_version_id')
                references_list = params_data.get('references', [])

                ver_id = uuid.uuid4().hex
                conn.execute(
                    '''INSERT INTO execution_versions (
                        id, campaign_id, slide_id, step_id, job_id, version_number,
                        provider_id, model_id, prompt, asset_id, actual_cost, status,
                        reason, requester, prompt_ref, references_json, parent_version_id, is_current,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?, ?, ?, ?, 1, ?)''',
                    (
                        ver_id, campaign_id, slide_id, step_id, job_id, ver_num,
                        job_dict['provider_id'], job_dict['model_id'], prompt_str, output_asset_id,
                        float(actual_cost), reason, requester, prompt_ref,
                        json.dumps(references_list, ensure_ascii=False), parent_version_id, now,
                    ),
                )

            # Verifica se todas as etapas da campanha foram concluídas
            remaining = conn.execute(
                "SELECT COUNT(*) FROM execution_jobs WHERE campaign_id=? AND status != 'completed'",
                (campaign_id,),
            ).fetchone()[0]

            if remaining == 0:
                conn.execute("UPDATE campaigns SET status='completed', updated_at=? WHERE id=?", (now, campaign_id))

            updated = conn.execute('SELECT * FROM execution_jobs WHERE id=?', (job_id,)).fetchone()

        # Checagem automática de fidelidade de produto fora da transação de escrita (Seção 27)
        if self.fidelity_service and slide_id and ver_id and output_asset_id:
            try:
                with sqlite3.connect(self.db.path) as c:
                    c.row_factory = sqlite3.Row
                    camp_row = c.execute('SELECT products_json FROM campaigns WHERE id=?', (campaign_id,)).fetchone()
                    if camp_row and camp_row['products_json']:
                        prods = json.loads(camp_row['products_json'])
                        if prods and isinstance(prods, list) and len(prods) > 0:
                            prod_id = prods[0].get('product_id')
                            if prod_id:
                                self.fidelity_service.check_fidelity(
                                    campaign_id=campaign_id,
                                    slide_id=slide_id,
                                    version_id=ver_id,
                                    product_id=prod_id,
                                    asset_id=output_asset_id,
                                    provider_id=job_dict['provider_id'],
                                    model_id=job_dict['model_id'],
                                )
            except Exception as e:
                logger.warning("Aviso na checagem automática de fidelidade: %s", e)

        return self._row_to_job(updated)

    def record_job_failure(
        self,
        job_id: str,
        error_message: str,
        status_code: Optional[int] = None,
        retry_allowed: bool = True,
    ) -> ExecutionJob:
        """Registra falha, gera diagnóstico estruturado (Seção 69) e executa retry finito sem custo inesperado (M05-A01, M05-A04)."""
        now = self._now()

        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.row_factory = sqlite3.Row
            job = conn.execute('SELECT * FROM execution_jobs WHERE id=?', (job_id,)).fetchone()
            if not job:
                raise ValueError(f"Trabalho '{job_id}' não encontrado.")
            job_dict = dict(job)

        campaign_id = job_dict['campaign_id']
        step_id = job_dict['step_id']
        attempt = int(job_dict['attempt'])
        max_retries = int(job_dict['max_retries'])
        est_cost = float(job_dict['estimated_cost'])
        res_id = job_dict['budget_reservation_id']

        diag = analyze_execution_failure(
            provider_id=job_dict['provider_id'],
            step_name=f"Etapa {step_id}",
            error_message=error_message,
            estimated_cost=est_cost,
            status_code=status_code,
        )

        will_retry = retry_allowed and (attempt < max_retries)

        if not will_retry and res_id:
            try:
                self.cost_manager.release_reservation(res_id)
            except Exception:
                pass

        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')

            if will_retry:
                conn.execute(
                    '''UPDATE execution_jobs
                       SET status='pending', locked_by=NULL, locked_at=NULL,
                           error_provider=?, error_step=?, error_probable_cause=?,
                           error_suggested_fix=?, error_potential_cost=?, updated_at=?
                       WHERE id=?''',
                    (diag.provider, diag.step, diag.probable_cause, diag.suggested_fix, diag.potential_cost, now, job_id),
                )
            else:
                conn.execute(
                    '''UPDATE execution_jobs
                       SET status='failed', locked_by=NULL, locked_at=NULL,
                           error_provider=?, error_step=?, error_probable_cause=?,
                           error_suggested_fix=?, error_potential_cost=?, updated_at=?
                       WHERE id=?''',
                    (diag.provider, diag.step, diag.probable_cause, diag.suggested_fix, diag.potential_cost, now, job_id),
                )
                conn.execute("UPDATE pipeline_steps SET status='failed', updated_at=? WHERE id=?", (now, step_id))
                conn.execute("UPDATE campaigns SET status='failed', updated_at=? WHERE id=?", (now, campaign_id))

            updated = conn.execute('SELECT * FROM execution_jobs WHERE id=?', (job_id,)).fetchone()
            return self._row_to_job(updated)

    def record_job_uncertain(
        self,
        job_id: str,
        error_message: str,
    ) -> ExecutionJob:
        """Marca trabalho como incerto em caso de timeout/interrupção de rede sem disparar nova cobrança (M05-A03)."""
        now = self._now()
        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')

            job = conn.execute('SELECT * FROM execution_jobs WHERE id=?', (job_id,)).fetchone()
            if not job:
                raise ValueError(f"Trabalho '{job_id}' não encontrado.")

            diag = FailureDiagnostic(
                provider=job['provider_id'].upper(),
                step=f"Etapa {job['step_id']}",
                probable_cause="Tempo limite de requisição atingido com resposta pendente do provedor.",
                suggested_fix="Reconcilie o resultado antes de nova tentativa para evitar cobrança duplicada.",
                potential_cost=float(job['estimated_cost']),
            )

            conn.execute(
                '''UPDATE execution_jobs
                   SET status='uncertain', uncertain_resolution='pending_reconciliation',
                       locked_by=NULL, locked_at=NULL, error_provider=?, error_step=?,
                       error_probable_cause=?, error_suggested_fix=?,
                       error_potential_cost=?, updated_at=?
                   WHERE id=?''',
                (diag.provider, diag.step, diag.probable_cause, diag.suggested_fix, diag.potential_cost, now, job_id),
            )

            updated = conn.execute('SELECT * FROM execution_jobs WHERE id=?', (job_id,)).fetchone()
            return self._row_to_job(updated)

    def reconcile_uncertain_job(
        self,
        job_id: str,
        outcome: str,
        actual_cost: float = 0.0,
        output_asset_id: Optional[str] = None,
    ) -> ExecutionJob:
        """Reconciliação manual/automática de resultado incerto evitando cobrança ou geração duplicada (M05-A03)."""
        clean_outcome = outcome.strip().lower()
        if clean_outcome not in ('success', 'failed'):
            raise ValueError("Resultado de reconciliação deve ser 'success' ou 'failed'.")

        if clean_outcome == 'success':
            return self.record_job_success(
                job_id=job_id,
                output_asset_id=output_asset_id or 'reconciled_asset',
                actual_cost=actual_cost,
                output_data={'reconciled': True},
            )
        else:
            return self.record_job_failure(
                job_id=job_id,
                error_message="Reconciliação confirmou falha ou não cobrança no provedor.",
                retry_allowed=False,
            )

    def pause_campaign(self, campaign_id: str) -> None:
        """Pausa a execução da campanha e de seus trabalhos pendentes preservando o concluído (M05-A02)."""
        now = self._now()
        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.execute("UPDATE campaigns SET status='paused', updated_at=? WHERE id=?", (now, campaign_id))
            conn.execute(
                "UPDATE execution_jobs SET status='paused', updated_at=? WHERE campaign_id=? AND status='pending'",
                (now, campaign_id),
            )

    def resume_campaign(self, campaign_id: str) -> None:
        """Retoma execução de trabalhos pausados sem duplicar trabalhos concluídos (M05-A02, M05-A03)."""
        now = self._now()
        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.execute("UPDATE campaigns SET status='running', updated_at=? WHERE id=?", (now, campaign_id))
            conn.execute(
                "UPDATE execution_jobs SET status='pending', updated_at=? WHERE campaign_id=? AND status='paused'",
                (now, campaign_id),
            )

    def pause_slide(self, slide_id: str) -> None:
        """Pausa os trabalhos de um slide específico (Seção 52)."""
        now = self._now()
        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.execute(
                "UPDATE execution_jobs SET status='paused', updated_at=? WHERE slide_id=? AND status='pending'",
                (now, slide_id),
            )

    def resume_slide(self, slide_id: str) -> None:
        """Retoma os trabalhos pausados de um slide específico (Seção 52)."""
        now = self._now()
        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.execute(
                "UPDATE execution_jobs SET status='pending', updated_at=? WHERE slide_id=? AND status='paused'",
                (now, slide_id),
            )

    def get_cancellation_impact(self, campaign_id: str) -> CancellationImpact:
        """Informa com precisão o custo já incorrido, risco de cobrança em voo e valor cancelável (M05-A02, Seção 52)."""
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            jobs = conn.execute('SELECT * FROM execution_jobs WHERE campaign_id=?', (campaign_id,)).fetchall()
            versions_count = conn.execute(
                'SELECT COUNT(*) FROM execution_versions WHERE campaign_id=?', (campaign_id,)
            ).fetchone()[0]

        completed_cost = sum(float(j['actual_cost']) for j in jobs if j['status'] == 'completed')
        in_flight_risk = sum(float(j['estimated_cost']) for j in jobs if j['status'] in ('running', 'uncertain'))
        cancellable_budget = sum(float(j['estimated_cost']) for j in jobs if j['status'] in ('pending', 'paused'))
        total_estimated = sum(float(j['estimated_cost']) for j in jobs)

        msg = (
            f"Cancelamento preservará {versions_count} versão(ões) concluída(s). "
            f"Custo incorrido irrecuperável: R$ {completed_cost:.2f}. "
            f"Risco de cobrança em voo: R$ {in_flight_risk:.2f}. "
            f"Orçamento poupado imediatamente: R$ {cancellable_budget:.2f}."
        )

        return CancellationImpact(
            campaign_id=campaign_id,
            completed_cost=completed_cost,
            in_flight_risk=in_flight_risk,
            cancellable_budget=cancellable_budget,
            total_estimated=total_estimated,
            preserved_versions_count=int(versions_count),
            message=msg,
        )

    def cancel_campaign(self, campaign_id: str, reason: str = 'Cancelado pelo usuário') -> CancellationImpact:
        """Cancela campanha e trabalhos pendentes, liberando reservas e preservando o concluído (M05-A02)."""
        now = self._now()
        impact = self.get_cancellation_impact(campaign_id)

        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.row_factory = sqlite3.Row
            cancellable_jobs = [dict(r) for r in conn.execute(
                "SELECT * FROM execution_jobs WHERE campaign_id=? AND status IN ('pending', 'paused')",
                (campaign_id,),
            ).fetchall()]

        for j in cancellable_jobs:
            res_id = j['budget_reservation_id']
            if res_id:
                try:
                    self.cost_manager.release_reservation(res_id)
                except Exception:
                    pass

        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute(
                "UPDATE execution_jobs SET status='cancelled', updated_at=? WHERE campaign_id=? AND status IN ('pending', 'paused')",
                (now, campaign_id),
            )
            conn.execute("UPDATE campaigns SET status='cancelled', updated_at=? WHERE id=?", (now, campaign_id))

        return impact

    def cancel_slide(self, slide_id: str) -> CancellationImpact:
        """Cancela trabalhos de um slide específico preservando os demais (Seções 51 e 52)."""
        now = self._now()
        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.row_factory = sqlite3.Row
            slide = conn.execute('SELECT * FROM storyboard_slides WHERE id=?', (slide_id,)).fetchone()
            if not slide:
                raise ValueError(f"Slide '{slide_id}' não encontrado.")
            campaign_id = slide['campaign_id']

            jobs = [dict(r) for r in conn.execute(
                "SELECT * FROM execution_jobs WHERE slide_id=? AND status IN ('pending', 'paused')",
                (slide_id,),
            ).fetchall()]

        for j in jobs:
            res_id = j['budget_reservation_id']
            if res_id:
                try:
                    self.cost_manager.release_reservation(res_id)
                except Exception:
                    pass

        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute(
                "UPDATE execution_jobs SET status='cancelled', updated_at=? WHERE slide_id=? AND status IN ('pending', 'paused')",
                (now, slide_id),
            )
            conn.execute("UPDATE storyboard_slides SET status='cancelled', updated_at=? WHERE id=?", (now, slide_id))

        return self.get_cancellation_impact(campaign_id)

    def cancel_job(self, job_id: str) -> CancellationImpact:
        """Cancela um trabalho individual da fila (Seção 52)."""
        now = self._now()
        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.row_factory = sqlite3.Row
            job = conn.execute('SELECT * FROM execution_jobs WHERE id=?', (job_id,)).fetchone()
            if not job:
                raise ValueError(f"Trabalho '{job_id}' não encontrado.")
            job_dict = dict(job)

        campaign_id = job_dict['campaign_id']
        res_id = job_dict['budget_reservation_id']
        if res_id and job_dict['status'] in ('pending', 'paused'):
            try:
                self.cost_manager.release_reservation(res_id)
            except Exception:
                pass

        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.execute("UPDATE execution_jobs SET status='cancelled', updated_at=? WHERE id=?", (now, job_id))

        return self.get_cancellation_impact(campaign_id)

    def regenerate_slide(
        self,
        campaign_id: str,
        slide_id: str,
        new_prompt: Optional[str] = None,
        engine_override: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> ExecutionJob:
        """Intervenção localizada: regenera somente o slide afetado e preserva todo o restante (Seção 51)."""
        now = self._now()
        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.row_factory = sqlite3.Row
            camp = conn.execute('SELECT * FROM campaigns WHERE id=?', (campaign_id,)).fetchone()
            slide = conn.execute('SELECT * FROM storyboard_slides WHERE id=?', (slide_id,)).fetchone()
            if not camp or not slide:
                raise ValueError("Campanha ou slide não encontrado.")

            step = conn.execute('SELECT * FROM pipeline_steps WHERE slide_id=?', (slide_id,)).fetchone()
            if not step:
                raise ValueError(f"Etapa de pipeline para o slide '{slide_id}' não encontrada.")
            step_dict = dict(step)
            slide_dict = dict(slide)

        prompt = (new_prompt or slide_dict['visual_prompt']).strip()
        prov_id = step_dict['provider_id']
        mod_id = step_dict['model_id']
        if engine_override and ':' in engine_override:
            p, m = engine_override.split(':', 1)
            prov_id = p.strip()
            mod_id = m.strip()

        cost = float(step_dict['estimated_cost'])
        res_id = self.cost_manager.reserve_budget(campaign_id, cost, approved=True)

        regen_key = f"{campaign_id}:{step_dict['id']}:regen:{uuid.uuid4().hex[:8]}"
        job_id = uuid.uuid4().hex

        merged_params = json.loads(step_dict['params_json'] or '{}')
        if params:
            merged_params.update(params)
        merged_params_json = json.dumps(merged_params, ensure_ascii=False)

        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')
            conn.execute(
                '''INSERT INTO execution_jobs (
                    id, campaign_id, slide_id, step_id, idempotency_key, status,
                    priority, attempt, max_retries, timeout_seconds, provider_id,
                    model_id, prompt, params_json, estimated_cost, actual_cost,
                    budget_reservation_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', 5, 0, 3, 30.0, ?, ?, ?, ?, ?, 0.0, ?, ?, ?)''',
                (
                    job_id, campaign_id, slide_id, step_dict['id'], regen_key,
                    prov_id, mod_id, prompt, merged_params_json, cost, res_id, now, now,
                )
            )
            conn.execute("UPDATE campaigns SET status='running', updated_at=? WHERE id=?", (now, campaign_id))
            job_row = conn.execute('SELECT * FROM execution_jobs WHERE id=?', (job_id,)).fetchone()
            return self._row_to_job(job_row)

    def get_job(self, job_id: str) -> Optional[ExecutionJob]:
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM execution_jobs WHERE id=?', (job_id,)).fetchone()
            return self._row_to_job(row) if row else None

    def list_jobs_for_campaign(self, campaign_id: str) -> List[ExecutionJob]:
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                'SELECT * FROM execution_jobs WHERE campaign_id=? ORDER BY priority ASC, created_at ASC',
                (campaign_id,),
            ).fetchall()
            return [self._row_to_job(r) for r in rows]

    def _row_to_version(self, r: sqlite3.Row) -> ExecutionVersion:
        keys = r.keys()
        ref_data = json.loads(r['references_json']) if 'references_json' in keys and r['references_json'] else []
        details_data = json.loads(r['fidelity_details_json']) if 'fidelity_details_json' in keys and r['fidelity_details_json'] else {}
        return ExecutionVersion(
            id=r['id'],
            campaign_id=r['campaign_id'],
            slide_id=r['slide_id'],
            step_id=r['step_id'],
            job_id=r['job_id'],
            version_number=int(r['version_number']),
            provider_id=r['provider_id'],
            model_id=r['model_id'],
            prompt=r['prompt'],
            asset_id=r['asset_id'],
            actual_cost=float(r['actual_cost']),
            status=r['status'],
            reason=r['reason'] if 'reason' in keys and r['reason'] else 'Geração inicial',
            requester=r['requester'] if 'requester' in keys and r['requester'] else 'system',
            prompt_ref=r['prompt_ref'] if 'prompt_ref' in keys else None,
            references=ref_data,
            fidelity_score=float(r['fidelity_score']) if 'fidelity_score' in keys and r['fidelity_score'] is not None else None,
            fidelity_details=details_data,
            fidelity_status=r['fidelity_status'] if 'fidelity_status' in keys and r['fidelity_status'] else 'pending',
            parent_version_id=r['parent_version_id'] if 'parent_version_id' in keys else None,
            is_current=bool(r['is_current']) if 'is_current' in keys else True,
            created_at=r['created_at'],
        )

    def get_version(self, version_id: str) -> Optional[ExecutionVersion]:
        """Recupera uma versão de execução preservada por ID (Seção 53)."""
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM execution_versions WHERE id=?', (version_id,)).fetchone()
            return self._row_to_version(row) if row else None

    def list_versions_for_slide(self, slide_id: str) -> List[ExecutionVersion]:
        """Lista todas as versões históricas preservadas de um slide (Seção 53, 80)."""
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                'SELECT * FROM execution_versions WHERE slide_id=? ORDER BY version_number ASC',
                (slide_id,),
            ).fetchall()
            return [self._row_to_version(r) for r in rows]

    def compare_versions(self, version_ids: List[str]) -> Dict[str, Any]:
        """Compara visualmente até 3 versões lado a lado exibindo metadados e diferenças (Seção 54)."""
        if not version_ids:
            raise ValueError("Selecione pelo menos uma versão para comparar.")
        if len(version_ids) > 3:
            raise ValueError("Permitido comparar no máximo 3 versões lado a lado (Seção 54).")

        versions = []
        for vid in version_ids:
            v = self.get_version(vid)
            if not v:
                raise ValueError(f"Versão '{vid}' não encontrada.")
            versions.append(v)

        engines = [f"{v.provider_id}:{v.model_id}" for v in versions]
        prompts = [v.prompt for v in versions]
        costs = [v.actual_cost for v in versions]
        fidelities = [v.fidelity_score for v in versions]

        engines_differ = len(set(engines)) > 1
        prompts_differ = len(set(prompts)) > 1
        costs_differ = len(set(costs)) > 1
        fidelities_differ = len(set(fidelities)) > 1

        differences = {
            'engines_differ': engines_differ,
            'engines': engines,
            'prompts_differ': prompts_differ,
            'cost_min': min(costs) if costs else 0.0,
            'cost_max': max(costs) if costs else 0.0,
            'cost_diff': round(max(costs) - min(costs), 4) if costs else 0.0,
            'fidelity_scores': fidelities,
            'fidelities_differ': fidelities_differ,
        }

        return {
            'slide_id': versions[0].slide_id,
            'campaign_id': versions[0].campaign_id,
            'versions': [v.to_dict() for v in versions],
            'differences': differences,
        }

    def choose_version(self, version_id: str, chooser: str = 'user') -> ExecutionVersion:
        """Define uma versão como a ativa/escolhida do slide, preservando histórico completo (Seção 54, 80)."""
        ver = self.get_version(version_id)
        if not ver:
            raise ValueError(f"Versão '{version_id}' não encontrada.")

        now = self._now()
        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute(
                'UPDATE execution_versions SET is_current = CASE WHEN id=? THEN 1 ELSE 0 END WHERE slide_id=?',
                (version_id, ver.slide_id),
            )
            engine_str = f"{ver.provider_id}:{ver.model_id}"
            conn.execute(
                "UPDATE storyboard_slides SET engine_override=?, updated_at=? WHERE id=?",
                (engine_str, now, ver.slide_id),
            )
        return self.get_version(version_id)

    def restore_version(self, version_id: str, restorer: str = 'user') -> ExecutionVersion:
        """Restaura uma versão anterior como ativa sem apagar as posteriores (Seção 53, 80, M06-A04)."""
        ver = self.get_version(version_id)
        if not ver:
            raise ValueError(f"Versão '{version_id}' não encontrada.")

        now = self._now()
        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute(
                'UPDATE execution_versions SET is_current = CASE WHEN id=? THEN 1 ELSE 0 END WHERE slide_id=?',
                (version_id, ver.slide_id),
            )
            engine_str = f"{ver.provider_id}:{ver.model_id}"
            conn.execute(
                "UPDATE storyboard_slides SET engine_override=?, updated_at=? WHERE id=?",
                (engine_str, now, ver.slide_id),
            )
        return self.get_version(version_id)

    def use_version_as_base(
        self,
        version_id: str,
        new_prompt: Optional[str] = None,
        requester: str = 'user',
    ) -> ExecutionJob:
        """Usa uma versão preservada como base para intervenção localizada no slide (Seção 53, 54, M06-A04)."""
        base = self.get_version(version_id)
        if not base:
            raise ValueError(f"Versão '{version_id}' não encontrada.")

        engine_override = f"{base.provider_id}:{base.model_id}"
        prompt = (new_prompt or base.prompt).strip()
        params = {
            'reason': f"Regeneração baseada na versão v{base.version_number}",
            'requester': requester,
            'parent_version_id': base.id,
            'base_version_number': base.version_number,
        }
        return self.regenerate_slide(
            campaign_id=base.campaign_id,
            slide_id=base.slide_id,
            new_prompt=prompt,
            engine_override=engine_override,
            params=params,
        )

    def record_version_learning(
        self,
        version_id: str,
        learning_note: str,
        recorder: str = 'user',
    ) -> str:
        """Registra aprendizado derivado de uma versão ou comparação (Seção 54, 80)."""
        clean_note = (learning_note or '').strip()
        if not clean_note:
            raise ValueError("Nota de aprendizado não pode ser vazia.")

        ver = self.get_version(version_id)
        if not ver:
            raise ValueError(f"Versão '{version_id}' não encontrada.")

        learning_id = uuid.uuid4().hex
        now = self._now()

        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.execute(
                '''INSERT INTO version_learnings (
                    id, campaign_id, slide_id, version_id, learning_note, action_taken, recorder, created_at
                ) VALUES (?, ?, ?, ?, ?, 'record_learning', ?, ?)''',
                (learning_id, ver.campaign_id, ver.slide_id, ver.id, clean_note, recorder, now),
            )

        if self.memory_store:
            try:
                self.memory_store.store_memory(
                    memory_type='creative_decision',
                    key=f"slide_learning_v{ver.version_number}",
                    value=f"Aprendizado na versão v{ver.version_number}: {clean_note}",
                    scope=ver.campaign_id,
                )
            except Exception as e:
                logger.warning("Aviso ao salvar aprendizado em memória tipada: %s", e)

        return learning_id

    def list_learnings_for_slide(self, slide_id: str) -> List[Dict[str, Any]]:
        """Lista aprendizados registrados para um slide (Seção 54, 80)."""
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                'SELECT * FROM version_learnings WHERE slide_id=? ORDER BY created_at DESC',
                (slide_id,),
            ).fetchall()
            return [dict(r) for r in rows]


    def _row_to_job(self, r: sqlite3.Row) -> ExecutionJob:
        diag = None
        if r['error_probable_cause']:
            diag = FailureDiagnostic(
                provider=r['error_provider'] or r['provider_id'],
                step=r['error_step'] or r['step_id'],
                probable_cause=r['error_probable_cause'],
                suggested_fix=r['error_suggested_fix'] or '',
                potential_cost=float(r['error_potential_cost'] or 0.0),
            )

        params = {}
        if r['params_json']:
            try:
                params = json.loads(r['params_json'])
            except Exception:
                pass

        out_data = {}
        if r['output_data_json']:
            try:
                out_data = json.loads(r['output_data_json'])
            except Exception:
                pass

        return ExecutionJob(
            id=r['id'],
            campaign_id=r['campaign_id'],
            slide_id=r['slide_id'],
            step_id=r['step_id'],
            idempotency_key=r['idempotency_key'],
            status=r['status'],
            priority=int(r['priority']),
            attempt=int(r['attempt']),
            max_retries=int(r['max_retries']),
            timeout_seconds=float(r['timeout_seconds']),
            provider_id=r['provider_id'],
            model_id=r['model_id'],
            prompt=r['prompt'],
            params=params,
            estimated_cost=float(r['estimated_cost']),
            actual_cost=float(r['actual_cost']),
            budget_reservation_id=r['budget_reservation_id'],
            output_asset_id=r['output_asset_id'],
            output_data=out_data,
            diagnostic=diag,
            uncertain_resolution=r['uncertain_resolution'],
            locked_by=r['locked_by'],
            locked_at=r['locked_at'],
            started_at=r['started_at'],
            completed_at=r['completed_at'],
            created_at=r['created_at'],
            updated_at=r['updated_at'],
        )
