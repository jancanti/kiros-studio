"""Gerenciador de Campanhas, Storyboard, Pipeline e Aprovações (M04)."""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from kiros.campaigns.models import (
    Campaign,
    StoryboardSlide,
    PipelineStep,
    CampaignApproval,
    VALID_CAMPAIGN_STATES,
    VALID_APPROVAL_MODES,
    VALID_STEP_TYPES,
    UnapprovedExecutionError,
    InvalidStateTransitionError,
    InvalidApprovalError,
)
from kiros.core.contracts import Provenance
from kiros.cost import CostManager
from kiros.infrastructure.local import SQLiteDatabase
from kiros.providers.router import ImageEngineRouter


class CampaignManager:
    """Gerencia o ciclo de vida completo de campanhas, storyboard, pipeline multi-engine e governança de aprovações."""

    def __init__(
        self,
        db: SQLiteDatabase,
        cost_manager: Optional[CostManager] = None,
        router: Optional[ImageEngineRouter] = None,
        queue: Optional[Any] = None,
        fidelity_service: Optional[Any] = None,
        layout_editor: Optional[Any] = None,
        template_library: Optional[Any] = None,
    ):
        self.db = db
        self.cost_manager = cost_manager
        self.router = router
        self.queue = queue
        self.fidelity_service = fidelity_service
        self.layout_editor = layout_editor
        self.template_library = template_library
        if self.queue is None and self.cost_manager is not None:
            from kiros.execution.queue import ExecutionQueue
            self.queue = ExecutionQueue(self.db, self.cost_manager, fidelity_service=self.fidelity_service)
        if self.layout_editor is None:
            from kiros.layout import LayoutEditor, LayoutEngine
            self.layout_editor = LayoutEditor(self.db, LayoutEngine())
        if self.template_library is None:
            from kiros.layout import TemplateLibrary
            self.template_library = TemplateLibrary(self.db)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_campaign(
        self,
        title: str,
        briefing: Dict[str, Any],
        strategy: Dict[str, Any],
        products: Optional[List[Dict[str, Any]]] = None,
        approval_mode: str = 'minimal',
        provenance: Optional[Provenance] = None,
    ) -> str:
        """Cria e persiste nova campanha no estado inicial 'draft' (M04-A01)."""
        clean_title = (title or '').strip()
        if not clean_title:
            raise ValueError('Título da campanha não pode ser vazio.')
        if approval_mode not in VALID_APPROVAL_MODES:
            raise ValueError(f"Modo de aprovação inválido: '{approval_mode}'. Suportados: {', '.join(VALID_APPROVAL_MODES)}")

        cid = uuid.uuid4().hex
        now = self._now()
        prov_source = provenance.source if provenance else 'user'
        products_val = products or []

        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''INSERT INTO campaigns (id, title, briefing_json, strategy_json, products_json, approval_mode, status, plan_version, created_at, updated_at, provenance)
                   VALUES (?, ?, ?, ?, ?, ?, 'draft', 1, ?, ?, ?)''',
                (
                    cid,
                    clean_title,
                    json.dumps(briefing or {}, ensure_ascii=False),
                    json.dumps(strategy or {}, ensure_ascii=False),
                    json.dumps(products_val, ensure_ascii=False),
                    approval_mode,
                    now,
                    now,
                    prov_source,
                ),
            )
        return cid

    def add_storyboard_slide(
        self,
        campaign_id: str,
        title: str,
        visual_prompt: str,
        framing: str = 'medium',
        caption_draft: str = '',
        engine_override: Optional[str] = None,
    ) -> str:
        """Adiciona slide ao storyboard e cria etapa mínima de pipeline com motor apropriado (Seções 10 e 23)."""
        clean_title = (title or '').strip()
        clean_prompt = (visual_prompt or '').strip()
        if not clean_title or not clean_prompt:
            raise ValueError('Título e prompt visual do slide são obrigatórios.')

        now = self._now()
        slide_id = uuid.uuid4().hex

        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            camp_row = conn.execute('SELECT * FROM campaigns WHERE id=?', (campaign_id,)).fetchone()
            if not camp_row:
                raise ValueError(f"Campanha '{campaign_id}' não encontrada.")

            # Próxima ordem do slide
            order_row = conn.execute(
                'SELECT COALESCE(MAX(slide_order), 0) + 1 FROM storyboard_slides WHERE campaign_id=?',
                (campaign_id,),
            ).fetchone()
            slide_order = int(order_row[0])

            conn.execute(
                '''INSERT INTO storyboard_slides (id, campaign_id, slide_order, title, visual_prompt, framing, caption_draft, engine_override, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?)''',
                (slide_id, campaign_id, slide_order, clean_title, clean_prompt, framing, caption_draft, engine_override, now, now),
            )

            # Invalida aprovações prévias e incrementa versão do plano (M04-A05)
            self._on_material_change(conn, campaign_id, reason=f"Adicionado slide '{clean_title}'")

        # Cria a etapa mínima necessária no pipeline (Seção 23: menor número de etapas necessário)
        self._generate_step_for_slide(campaign_id, slide_id, clean_prompt, engine_override)

        # Cria layout padrão para o slide (Seção 28 e 29)
        if self.layout_editor:
            self.layout_editor.get_or_create_layout(
                campaign_id=campaign_id,
                slide_id=slide_id,
                target_format='4:5',
                default_headline=clean_title,
            )

        return slide_id

    def _resolve_engine_for_slide(self, campaign_id: str, engine_override: Optional[str]) -> Tuple[str, str, float]:
        """Resolve engine para um slide: override manual > recomendação do router > fallback Gemini."""
        if engine_override and ':' in engine_override:
            p_id, m_id = engine_override.split(':', 1)
            cost = self._estimate_step_cost(p_id, m_id)
            return p_id.strip(), m_id.strip(), cost

        # Consulta recomendação automática do ImageEngineRouter se disponível
        if self.router:
            rec = self.router.recommend({'type': 'ambient'})
            provider_id = rec.get('provider_id', 'gemini')
            model_id = rec.get('model_id', 'imagen-3.0-generate-002')
            estimated_cost = rec.get('estimated_cost', 0.16)
            return provider_id, model_id, float(estimated_cost)

        return 'gemini', 'imagen-3.0-generate-002', 0.16

    def _estimate_step_cost(self, provider_id: str, model_id: str) -> float:
        if self.cost_manager:
            try:
                return float(self.cost_manager.estimate_cost(provider_id, model_id, count=1))
            except Exception:
                pass
        # Preços padrão oficiais vigentes
        if provider_id == 'gemini':
            return 0.16 if 'fast' not in model_id else 0.08
        if provider_id == 'openai':
            return 0.20 if 'dall-e-3' in model_id else 0.10
        if provider_id == 'firefly':
            return 0.14
        return 0.12

    def _generate_step_for_slide(
        self,
        campaign_id: str,
        slide_id: str,
        visual_prompt: str,
        engine_override: Optional[str] = None,
    ) -> str:
        """Gera etapa direta de geração no pipeline (etapa única e enxuta por slide, Seção 23)."""
        provider_id, model_id, cost = self._resolve_engine_for_slide(campaign_id, engine_override)
        step_id = uuid.uuid4().hex
        now = self._now()

        with sqlite3.connect(self.db.path) as conn:
            order_row = conn.execute(
                'SELECT COALESCE(MAX(step_order), 0) + 1 FROM pipeline_steps WHERE campaign_id=?',
                (campaign_id,),
            ).fetchone()
            step_order = int(order_row[0])

            params = {
                'prompt': visual_prompt,
                'aspect_ratio': '1:1',
                'quality': 'standard',
            }

            conn.execute(
                '''INSERT INTO pipeline_steps (id, campaign_id, slide_id, step_order, step_type, name, provider_id, model_id, params_json, estimated_cost, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'generation', ?, ?, ?, ?, ?, 'draft', ?, ?)''',
                (
                    step_id,
                    campaign_id,
                    slide_id,
                    step_order,
                    f"Geração de Imagem com {model_id}",
                    provider_id,
                    model_id,
                    json.dumps(params, ensure_ascii=False),
                    cost,
                    now,
                    now,
                ),
            )
        return step_id

    def update_pipeline_step(
        self,
        step_id: str,
        name: Optional[str] = None,
        provider_id: Optional[str] = None,
        model_id: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Edição localizada de etapa: preserva o restante do pipeline sem alterar etapas não afetadas (Seção 31 e M04-A02)."""
        now = self._now()
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            step_row = conn.execute('SELECT * FROM pipeline_steps WHERE id=?', (step_id,)).fetchone()
            if not step_row:
                raise ValueError(f"Etapa de pipeline '{step_id}' não encontrada.")

            campaign_id = step_row['campaign_id']
            new_name = (name if name is not None else step_row['name']).strip()
            new_prov = (provider_id if provider_id is not None else step_row['provider_id']).strip()
            new_model = (model_id if model_id is not None else step_row['model_id']).strip()

            current_params = json.loads(step_row['params_json'])
            if params is not None:
                current_params.update(params)

            new_cost = self._estimate_step_cost(new_prov, new_model)

            conn.execute(
                '''UPDATE pipeline_steps
                   SET name=?, provider_id=?, model_id=?, params_json=?, estimated_cost=?, status='draft', updated_at=?
                   WHERE id=?''',
                (new_name, new_prov, new_model, json.dumps(current_params, ensure_ascii=False), new_cost, now, step_id),
            )

            # Mudança material: incrementa a versão do plano da campanha e invalida aprovação prévia (M04-A05)
            self._on_material_change(conn, campaign_id, reason=f"Edição localizada na etapa '{new_name}'")

    def update_slide_engine(self, slide_id: str, engine_override: str) -> None:
        """Altera o motor de um slide específico preservando as outras etapas intactas (M04-A02)."""
        clean_override = (engine_override or '').strip()
        now = self._now()

        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            slide_row = conn.execute('SELECT * FROM storyboard_slides WHERE id=?', (slide_id,)).fetchone()
            if not slide_row:
                raise ValueError(f"Slide '{slide_id}' não encontrado.")

            campaign_id = slide_row['campaign_id']

            conn.execute(
                'UPDATE storyboard_slides SET engine_override=?, updated_at=? WHERE id=?',
                (clean_override, now, slide_id),
            )

            # Atualiza apenas a etapa de pipeline ligada a este slide
            if clean_override and ':' in clean_override:
                prov_id, mod_id = clean_override.split(':', 1)
                cost = self._estimate_step_cost(prov_id, mod_id)
                conn.execute(
                    '''UPDATE pipeline_steps
                       SET provider_id=?, model_id=?, estimated_cost=?, name=?, status='draft', updated_at=?
                       WHERE slide_id=?''',
                    (prov_id, mod_id, cost, f"Geração de Imagem com {mod_id}", now, slide_id),
                )

            # Mudança material: invalida aprovação e incrementa versão
            self._on_material_change(conn, campaign_id, reason=f"Alteração de engine no slide '{slide_row['title']}'")

    def _on_material_change(self, conn: sqlite3.Connection, campaign_id: str, reason: str) -> None:
        """Regra de Ouro (M04-A05): Toda alteração material incrementa plan_version e invalida aprovações prévias."""
        now = self._now()

        # Invalida aprovações existentes
        conn.execute(
            '''UPDATE campaign_approvals
               SET is_valid=0, invalidation_reason=?
               WHERE campaign_id=? AND is_valid=1''',
            (reason, campaign_id),
        )

        # Incrementa plan_version e rebaixa status caso estivesse aprovada ou aguardando
        conn.execute(
            '''UPDATE campaigns
               SET plan_version = plan_version + 1,
                   status = CASE WHEN status IN ('approved', 'awaiting_approval') THEN 'draft' ELSE status END,
                   approved_version = NULL,
                   approved_at = NULL,
                   approved_by = NULL,
                   updated_at = ?
               WHERE id = ?''',
            (now, campaign_id),
        )

    def submit_for_approval(self, campaign_id: str) -> None:
        """Submete a campanha para a tela de aprovação (transição draft -> awaiting_approval)."""
        now = self._now()
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            camp = conn.execute('SELECT * FROM campaigns WHERE id=?', (campaign_id,)).fetchone()
            if not camp:
                raise ValueError(f"Campanha '{campaign_id}' não encontrada.")

            slides_count = conn.execute('SELECT COUNT(*) FROM storyboard_slides WHERE campaign_id=?', (campaign_id,)).fetchone()[0]
            if slides_count == 0:
                raise ValueError('Não é possível submeter uma campanha sem nenhum slide no storyboard.')

            if camp['status'] not in ('draft', 'awaiting_approval'):
                raise InvalidStateTransitionError(f"Campanha no estado '{camp['status']}' não pode ser submetida para aprovação.")

            conn.execute("UPDATE campaigns SET status='awaiting_approval', updated_at=? WHERE id=?", (now, campaign_id))

    def approve_campaign(
        self,
        campaign_id: str,
        approver: str = 'user',
        confirm_budget: bool = True,
    ) -> CampaignApproval:
        """Aprova a campanha inteira ou conjunto para o plan_version atual (M04-A04)."""
        now = self._now()
        clean_approver = (approver or 'user').strip()

        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            camp = conn.execute('SELECT * FROM campaigns WHERE id=?', (campaign_id,)).fetchone()
            if not camp:
                raise ValueError(f"Campanha '{campaign_id}' não encontrada.")

            if camp['status'] not in ('draft', 'awaiting_approval'):
                raise InvalidStateTransitionError(f"Campanha no estado '{camp['status']}' não pode ser aprovada.")

            # Calcula custo total estimado
            cost_row = conn.execute(
                'SELECT COALESCE(SUM(estimated_cost), 0.0) FROM pipeline_steps WHERE campaign_id=?',
                (campaign_id,),
            ).fetchone()
            total_cost = float(cost_row[0])

            current_version = int(camp['plan_version'])
            appr_id = uuid.uuid4().hex

            # Reserva de orçamento via CostManager se ativo
            res_id = None
            if self.cost_manager and total_cost > 0 and confirm_budget:
                try:
                    res_id = self.cost_manager.reserve_budget(
                        campaign_id=campaign_id,
                        amount=total_cost,
                        stage='approval_plan',
                    )
                except Exception:
                    # Se não puder reservar orçamento, não impede aprovação local mas anota
                    res_id = f"local-res-{uuid.uuid4().hex[:8]}"

            # Registra aprovação formal vinculada à versão exata do plano
            conn.execute(
                '''INSERT INTO campaign_approvals (id, campaign_id, step_id, plan_version, approved_by, approved_at, estimated_cost, budget_reservation_id, is_valid, invalidation_reason)
                   VALUES (?, ?, NULL, ?, ?, ?, ?, ?, 1, NULL)''',
                (appr_id, campaign_id, current_version, clean_approver, now, total_cost, res_id),
            )

            # Atualiza campanha para 'approved'
            conn.execute(
                '''UPDATE campaigns
                   SET status='approved',
                       approved_version=?,
                       approved_at=?,
                       approved_by=?,
                       budget_limit=?,
                       updated_at=?
                   WHERE id=?''',
                (current_version, now, clean_approver, total_cost, now, campaign_id),
            )

            # Atualiza todas as etapas para approved
            conn.execute("UPDATE pipeline_steps SET status='approved', updated_at=? WHERE campaign_id=?", (now, campaign_id))

            return CampaignApproval(
                id=appr_id,
                campaign_id=campaign_id,
                step_id=None,
                plan_version=current_version,
                approved_by=clean_approver,
                approved_at=now,
                estimated_cost=total_cost,
                budget_reservation_id=res_id,
                is_valid=True,
            )

    def approve_step(self, step_id: str, approver: str = 'user') -> CampaignApproval:
        """Aprova uma etapa individual (modo step_by_step ou full_control, M04-A04)."""
        now = self._now()
        clean_approver = (approver or 'user').strip()

        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            step_row = conn.execute('SELECT * FROM pipeline_steps WHERE id=?', (step_id,)).fetchone()
            if not step_row:
                raise ValueError(f"Etapa '{step_id}' não encontrada.")

            campaign_id = step_row['campaign_id']
            camp = conn.execute('SELECT * FROM campaigns WHERE id=?', (campaign_id,)).fetchone()
            current_version = int(camp['plan_version'])
            cost = float(step_row['estimated_cost'])
            appr_id = uuid.uuid4().hex

            conn.execute("UPDATE pipeline_steps SET status='approved', updated_at=? WHERE id=?", (now, step_id))

            conn.execute(
                '''INSERT INTO campaign_approvals (id, campaign_id, step_id, plan_version, approved_by, approved_at, estimated_cost, budget_reservation_id, is_valid, invalidation_reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 1, NULL)''',
                (appr_id, campaign_id, step_id, current_version, clean_approver, now, cost),
            )

            # Verifica se todas as etapas foram aprovadas
            unapproved = conn.execute(
                "SELECT COUNT(*) FROM pipeline_steps WHERE campaign_id=? AND status != 'approved'",
                (campaign_id,),
            ).fetchone()[0]

            if unapproved == 0:
                conn.execute(
                    '''UPDATE campaigns
                       SET status='approved', approved_version=?, approved_at=?, approved_by=?, updated_at=?
                       WHERE id=?''',
                    (current_version, now, clean_approver, now, campaign_id),
                )

            return CampaignApproval(
                id=appr_id,
                campaign_id=campaign_id,
                step_id=step_id,
                plan_version=current_version,
                approved_by=clean_approver,
                approved_at=now,
                estimated_cost=cost,
                is_valid=True,
            )

    def queue_execution(self, campaign_id: str) -> None:
        """Enfileira campanha para execução. RECUSA no servidor se não houver aprovação válida (M04-A05, M05-A01)."""
        now = self._now()
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            camp = conn.execute('SELECT * FROM campaigns WHERE id=?', (campaign_id,)).fetchone()
            if not camp:
                raise ValueError(f"Campanha '{campaign_id}' não encontrada.")

            # Checagem rigorosa de aprovação vinculada à versão do plano (M04-A05)
            current_version = int(camp['plan_version'])
            if camp['status'] != 'approved' or camp['approved_version'] != current_version:
                raise UnapprovedExecutionError(
                    f"Execução recusada: Campanha '{campaign_id}' não possui aprovação válida para a versão atual do plano (v{current_version}). "
                    f"Aprove o plano antes de enfileirar."
                )

            # Verifica aprovação ativa registrada
            valid_approval = conn.execute(
                'SELECT 1 FROM campaign_approvals WHERE campaign_id=? AND plan_version=? AND is_valid=1',
                (campaign_id, current_version),
            ).fetchone()
            if not valid_approval:
                raise UnapprovedExecutionError(
                    f"Execução recusada: Nenhuma aprovação ativa e válida encontrada para a versão {current_version}."
                )

        if self.queue:
            self.queue.enqueue_campaign_execution(campaign_id)
        else:
            with sqlite3.connect(self.db.path) as conn:
                conn.execute("UPDATE campaigns SET status='queued', updated_at=? WHERE id=?", (now, campaign_id))
                conn.execute("UPDATE pipeline_steps SET status='queued', updated_at=? WHERE campaign_id=?", (now, campaign_id))

    def cancel_campaign(self, campaign_id: str, reason: str = 'Cancelado pelo usuário') -> Any:
        """Cancela campanha e libera reservas de orçamento preservando o concluído (Seção 52, 66)."""
        if self.queue:
            return self.queue.cancel_campaign(campaign_id, reason=reason)
        now = self._now()
        with sqlite3.connect(self.db.path) as conn:
            conn.execute("UPDATE campaigns SET status='cancelled', updated_at=? WHERE id=?", (now, campaign_id))
            conn.execute("UPDATE pipeline_steps SET status='cancelled', updated_at=? WHERE campaign_id=?", (now, campaign_id))
        return None

    def pause_campaign(self, campaign_id: str) -> None:
        """Pausa a execução da campanha (Seção 52)."""
        if self.queue:
            self.queue.pause_campaign(campaign_id)
        else:
            with sqlite3.connect(self.db.path) as conn:
                conn.execute("UPDATE campaigns SET status='paused', updated_at=? WHERE id=?", (self._now(), campaign_id))

    def resume_campaign(self, campaign_id: str) -> None:
        """Retoma a execução da campanha (Seção 52)."""
        if self.queue:
            self.queue.resume_campaign(campaign_id)
        else:
            with sqlite3.connect(self.db.path) as conn:
                conn.execute("UPDATE campaigns SET status='running', updated_at=? WHERE id=?", (self._now(), campaign_id))

    def regenerate_slide(self, campaign_id: str, slide_id: str, new_prompt: Optional[str] = None, engine_override: Optional[str] = None) -> Any:
        """Intervenção localizada: regenera somente o slide afetado e preserva os demais (Seção 51)."""
        if self.queue:
            return self.queue.regenerate_slide(campaign_id, slide_id, new_prompt=new_prompt, engine_override=engine_override)
        raise RuntimeError("Fila de execução não configurada para regeneração.")

    def get_cancellation_impact(self, campaign_id: str) -> Any:
        """Retorna demonstrativo de impacto financeiro e risco de cobrança (Seção 52)."""
        if self.queue:
            return self.queue.get_cancellation_impact(campaign_id)
        return None

    def set_monitoring_mode(self, campaign_id: str, mode: str) -> None:
        """Define o modo de monitoramento da campanha (Seção 50)."""
        if self.queue:
            self.queue.set_monitoring_mode(campaign_id, mode)

    def get_monitoring_mode(self, campaign_id: str) -> str:
        """Recupera o modo de monitoramento da campanha (Seção 50)."""
        if self.queue:
            return self.queue.get_monitoring_mode(campaign_id)
        return 'supervised'

    def list_jobs(self, campaign_id: str) -> List[Any]:
        """Lista trabalhos da fila para a campanha."""
        if self.queue:
            return self.queue.list_jobs_for_campaign(campaign_id)
        return []

    def list_slide_versions(self, slide_id: str) -> List[Any]:
        """Lista versões geradas de um slide."""
        if self.queue:
            return self.queue.list_versions_for_slide(slide_id)
        return []

    def get_campaign(self, campaign_id: str) -> Optional[Campaign]:
        """Recupera a campanha estruturada completa com slides, pipeline e histórico de aprovações."""
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM campaigns WHERE id=?', (campaign_id,)).fetchone()
            if not row:
                return None

            # Slides
            slide_rows = conn.execute(
                'SELECT * FROM storyboard_slides WHERE campaign_id=? ORDER BY slide_order ASC',
                (campaign_id,),
            ).fetchall()
            slides = [
                StoryboardSlide(
                    id=s['id'],
                    campaign_id=s['campaign_id'],
                    slide_order=s['slide_order'],
                    title=s['title'],
                    visual_prompt=s['visual_prompt'],
                    framing=s['framing'],
                    caption_draft=s['caption_draft'],
                    engine_override=s['engine_override'],
                    status=s['status'],
                    created_at=s['created_at'],
                    updated_at=s['updated_at'],
                )
                for s in slide_rows
            ]

            # Steps
            step_rows = conn.execute(
                'SELECT * FROM pipeline_steps WHERE campaign_id=? ORDER BY step_order ASC',
                (campaign_id,),
            ).fetchall()
            steps = [
                PipelineStep(
                    id=p['id'],
                    campaign_id=p['campaign_id'],
                    slide_id=p['slide_id'],
                    step_order=p['step_order'],
                    step_type=p['step_type'],
                    name=p['name'],
                    provider_id=p['provider_id'],
                    model_id=p['model_id'],
                    params=json.loads(p['params_json']),
                    estimated_cost=float(p['estimated_cost']),
                    status=p['status'],
                    created_at=p['created_at'],
                    updated_at=p['updated_at'],
                )
                for p in step_rows
            ]

            # Approvals
            appr_rows = conn.execute(
                'SELECT * FROM campaign_approvals WHERE campaign_id=? ORDER BY approved_at DESC',
                (campaign_id,),
            ).fetchall()
            approvals = [
                CampaignApproval(
                    id=a['id'],
                    campaign_id=a['campaign_id'],
                    step_id=a['step_id'],
                    plan_version=int(a['plan_version']),
                    approved_by=a['approved_by'],
                    approved_at=a['approved_at'],
                    estimated_cost=float(a['estimated_cost']),
                    budget_reservation_id=a['budget_reservation_id'],
                    is_valid=bool(a['is_valid']),
                    invalidation_reason=a['invalidation_reason'],
                )
                for a in appr_rows
            ]

            return Campaign(
                id=row['id'],
                title=row['title'],
                briefing=json.loads(row['briefing_json']),
                strategy=json.loads(row['strategy_json']),
                products=json.loads(row['products_json']),
                approval_mode=row['approval_mode'],
                status=row['status'],
                plan_version=int(row['plan_version']),
                approved_version=int(row['approved_version']) if row['approved_version'] is not None else None,
                approved_at=row['approved_at'],
                approved_by=row['approved_by'],
                budget_limit=float(row['budget_limit']) if row['budget_limit'] is not None else None,
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                provenance=row['provenance'],
                slides=slides,
                pipeline_steps=steps,
                approvals=approvals,
            )

    def list_campaigns(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lista resumo de campanhas para visualização geral."""
        query = 'SELECT * FROM campaigns WHERE 1=1'
        params: List[Any] = []
        if status:
            query += ' AND status = ?'
            params.append(status)
        query += ' ORDER BY updated_at DESC'

        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, tuple(params)).fetchall()
            result = []
            for r in rows:
                cid = r['id']
                slides_cnt = conn.execute('SELECT COUNT(*) FROM storyboard_slides WHERE campaign_id=?', (cid,)).fetchone()[0]
                cost = conn.execute('SELECT COALESCE(SUM(estimated_cost), 0.0) FROM pipeline_steps WHERE campaign_id=?', (cid,)).fetchone()[0]
                result.append({
                    'id': cid,
                    'title': r['title'],
                    'status': r['status'],
                    'approval_mode': r['approval_mode'],
                    'plan_version': r['plan_version'],
                    'slides_count': slides_cnt,
                    'estimated_cost': round(float(cost), 4),
                    'created_at': r['created_at'],
                    'updated_at': r['updated_at'],
                })
            return result

    def get_approval_screen_data(self, campaign_id: str) -> Dict[str, Any]:
        """Compila dados para a Tela de Aprovação (Seção 75 e M04-A03)."""
        campaign = self.get_campaign(campaign_id)
        if not campaign:
            raise ValueError(f"Campanha '{campaign_id}' não encontrada.")

        briefing = campaign.briefing
        strategy = campaign.strategy
        total_cost = sum(s.estimated_cost for s in campaign.pipeline_steps)
        total_generations = len(campaign.slides)

        engines_summary = []
        for s in campaign.slides:
            eng = s.engine_override or "Padrão (Google Gemini Imagen 3)"
            engines_summary.append(f"Slide {s.slide_order}: {eng}")

        is_validly_approved = (
            campaign.status in ('approved', 'queued', 'running', 'paused', 'completed')
            and campaign.approved_version == campaign.plan_version
            and any(a.is_valid and a.plan_version == campaign.plan_version for a in campaign.approvals)
        )

        return {
            'campaign_id': campaign.id,
            'title': campaign.title,
            'objective': briefing.get('primary_objective', 'awareness').upper(),
            'secondary_objective': briefing.get('secondary_objective', 'relacionamento'),
            'concept': briefing.get('summary', briefing.get('raw_briefing', campaign.title)),
            'visual_tone': briefing.get('visual_tone', 'Minimalista e contemporâneo'),
            'products': campaign.products,
            'storyboard': [s.to_dict() for s in campaign.slides],
            'engine_summary': engines_summary,
            'pipeline': [p.to_dict() for p in campaign.pipeline_steps],
            'estimated_generations': total_generations,
            'estimated_cost': round(total_cost, 4),
            'confidence': briefing.get('confidence', 0.90),
            'approval_mode': campaign.approval_mode,
            'status': campaign.status,
            'plan_version': campaign.plan_version,
            'is_approved': is_validly_approved,
            'approved_by': campaign.approved_by,
            'approved_at': campaign.approved_at,
        }

    def compare_slide_versions(self, version_ids: List[str]) -> Dict[str, Any]:
        """Compara visualmente até 3 versões de slides lado a lado (Seção 54)."""
        if not self.queue:
            raise RuntimeError("Fila de execução não configurada.")
        return self.queue.compare_versions(version_ids)

    def choose_slide_version(self, version_id: str, chooser: str = 'user') -> Any:
        """Define uma versão como ativa para o slide (Seção 54, 80)."""
        if not self.queue:
            raise RuntimeError("Fila de execução não configurada.")
        return self.queue.choose_version(version_id, chooser)

    def restore_slide_version(self, version_id: str, restorer: str = 'user') -> Any:
        """Restaura versão anterior mantendo histórico preservado (Seção 53, 80)."""
        if not self.queue:
            raise RuntimeError("Fila de execução não configurada.")
        return self.queue.restore_version(version_id, restorer)

    def use_version_as_base(
        self,
        version_id: str,
        new_prompt: Optional[str] = None,
        requester: str = 'user',
    ) -> Any:
        """Usa versão preservada como base para intervenção localizada no slide (Seção 53, 54)."""
        if not self.queue:
            raise RuntimeError("Fila de execução não configurada.")
        return self.queue.use_version_as_base(version_id, new_prompt, requester)

    def record_version_learning(
        self,
        version_id: str,
        learning_note: str,
        recorder: str = 'user',
    ) -> str:
        """Registra aprendizado na memória tipada e histórico (Seção 54, 80)."""
        if not self.queue:
            raise RuntimeError("Fila de execução não configurada.")
        return self.queue.record_version_learning(version_id, learning_note, recorder)

    def list_learnings_for_slide(self, slide_id: str) -> List[Dict[str, Any]]:
        if not self.queue:
            return []
        return self.queue.list_learnings_for_slide(slide_id)

    # -------------------------------------------------------------
    # Métodos de Layout e Design Determinístico (Seções 28, 29, 30)
    # -------------------------------------------------------------

    def get_slide_layout(self, slide_id: str) -> Any:
        """Recupera layout associado a um slide ou gera o padrão."""
        if not self.layout_editor:
            raise RuntimeError("LayoutEditor não configurado.")
        # Localiza campaign_id e título do slide
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT campaign_id, title FROM storyboard_slides WHERE id=?', (slide_id,)).fetchone()
            if not row:
                raise ValueError(f"Slide '{slide_id}' não encontrado.")
            cid = row['campaign_id']
            title = row['title']
        return self.layout_editor.get_or_create_layout(cid, slide_id, default_headline=title)

    def update_slide_layout(
        self,
        layout_id: str,
        updates: Dict[str, Any],
        confirm_protected: bool = False,
        unlock_critical: bool = False,
        audit_reason: Optional[str] = None,
        unlocked_by: Optional[str] = None,
    ) -> Tuple[Any, List[str]]:
        """Atualiza atributos do layout com governança verde/amarelo/vermelho (Seção 29)."""
        if not self.layout_editor:
            raise RuntimeError("LayoutEditor não configurado.")
        return self.layout_editor.update_layout(
            layout_id=layout_id,
            updates=updates,
            confirm_protected=confirm_protected,
            unlock_critical=unlock_critical,
            audit_reason=audit_reason,
            unlocked_by=unlocked_by,
        )

    def switch_slide_layout_format(self, layout_id: str, target_format: str) -> Any:
        """Altera o formato do layout entre 4:5 e 9:16 com adaptação responsiva."""
        if not self.layout_editor:
            raise RuntimeError("LayoutEditor não configurado.")
        return self.layout_editor.switch_format(layout_id, target_format)

    def apply_template_to_slide(
        self,
        layout_id: str,
        template_id: str,
        experimental_authorized: bool = False,
    ) -> Any:
        """Aplica template da biblioteca ao layout do slide (Seção 30)."""
        if not self.layout_editor or not self.template_library:
            raise RuntimeError("Editor ou Biblioteca de Templates não configurados.")
        layout = self.layout_editor.get_layout(layout_id)
        if not layout:
            raise ValueError(f"Layout '{layout_id}' não encontrado.")
        return self.template_library.apply_template(
            template_id=template_id,
            layout=layout,
            experimental_authorized=experimental_authorized,
        )

    def detect_template_overuse(self, template_id: str) -> Dict[str, Any]:
        """Detecta sobreuso de template para preservar diversidade visual da marca (Seções 30 e 32)."""
        if not self.template_library:
            raise RuntimeError("TemplateLibrary não configurada.")
        return self.template_library.detect_overuse(template_id)

    def save_slide_layout_as_template(
        self,
        layout_id: str,
        name: str,
        family: str,
        status: str = 'active',
        provenance_source: str = 'user',
    ) -> Any:
        """Salva uma composição aprovada como template na biblioteca (Seção 30)."""
        if not self.layout_editor or not self.template_library:
            raise RuntimeError("Editor ou Biblioteca de Templates não configurados.")
        layout = self.layout_editor.get_layout(layout_id)
        if not layout:
            raise ValueError(f"Layout '{layout_id}' não encontrado.")
        return self.template_library.save_composition_as_template(
            layout=layout,
            name=name,
            family=family,
            status=status,
            provenance_source=provenance_source,
        )

    def render_slide_svg(self, layout_id: str, show_safe_areas: bool = False) -> str:
        """Renderiza o SVG determinístico do slide sem LLM."""
        if not self.layout_editor:
            raise RuntimeError("LayoutEditor não configurado.")
        layout = self.layout_editor.get_layout(layout_id)
        if not layout:
            raise ValueError(f"Layout '{layout_id}' não encontrado.")
        return self.layout_editor.engine.render_svg(layout, show_safe_areas=show_safe_areas)

    def export_slide_layout(self, layout_id: str) -> Dict[str, Any]:
        """Exporta dados completos e SVG determinístico do layout."""
        if not self.layout_editor:
            raise RuntimeError("LayoutEditor não configurado.")
        layout = self.layout_editor.get_layout(layout_id)
        if not layout:
            raise ValueError(f"Layout '{layout_id}' não encontrado.")
        return self.layout_editor.engine.export_layout_data(layout)


