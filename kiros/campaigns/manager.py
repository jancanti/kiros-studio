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
from kiros.content import (
    CaptionContent,
    StorySequence,
    StoryFrame,
    PrePublishAuditResult,
    CopyEngine,
    StoriesEngine,
    PrePublishAuditor,
    VALID_CAPTION_MODES,
    VALID_CTA_MODES,
    VALID_STORY_TYPES,
)


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
        copy_engine: Optional[Any] = None,
        stories_engine: Optional[Any] = None,
        pre_publish_auditor: Optional[Any] = None,
        library: Optional[Any] = None,
    ):
        self.db = db
        self.cost_manager = cost_manager
        self.router = router
        self.queue = queue
        self.fidelity_service = fidelity_service
        self.layout_editor = layout_editor
        self.template_library = template_library
        self.copy_engine = copy_engine or CopyEngine()
        self.stories_engine = stories_engine or StoriesEngine()
        self.pre_publish_auditor = pre_publish_auditor or PrePublishAuditor(self.copy_engine, self.stories_engine)
        self.library = library
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

        # Cria cópia/legenda padrão para o slide (Seções 34-37 e M08)
        self.get_or_create_slide_copy(
            campaign_id=campaign_id,
            slide_id=slide_id,
            initial_caption=caption_draft,
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

    # -------------------------------------------------------------
    # Seções 34, 35, 36, 37: Copy, Legendas, Voz e Governança de Preço
    # -------------------------------------------------------------

    def get_product_for_slide(self, slide_id: str) -> Dict[str, Any]:
        """Recupera dados oficiais do produto associado ao slide (da Product Bible / campanha)."""
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            s_row = conn.execute('SELECT campaign_id FROM storyboard_slides WHERE id=?', (slide_id,)).fetchone()
            if not s_row:
                return {}
            c_row = conn.execute('SELECT products_json FROM campaigns WHERE id=?', (s_row['campaign_id'],)).fetchone()
            if not c_row:
                return {}
            prods = json.loads(c_row['products_json'])
            if not prods:
                return {}
            first_prod = prods[0]
            prod_id = first_prod.get('product_id') or first_prod.get('id')

            # Tenta buscar versão oficial da Product Bible se existir
            if prod_id:
                pb_row = conn.execute(
                    'SELECT content FROM bible_versions WHERE kind=? AND owner=? AND approved_at IS NOT NULL ORDER BY version DESC LIMIT 1',
                    ('product', prod_id),
                ).fetchone()
                if pb_row:
                    try:
                        pb_data = json.loads(pb_row['content'])
                        merged = dict(first_prod)
                        merged.update(pb_data)
                        return merged
                    except Exception:
                        pass
            return first_prod

    def get_or_create_slide_copy(
        self,
        campaign_id: str,
        slide_id: str,
        initial_caption: str = '',
    ) -> CaptionContent:
        """Recupera ou inicializa a cópia/legenda associada ao slide (Seções 34-37)."""
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM slide_copies WHERE slide_id=?', (slide_id,)).fetchone()
            if row:
                return CaptionContent(
                    id=row['id'],
                    campaign_id=row['campaign_id'],
                    slide_id=row['slide_id'],
                    mode=row['mode'],
                    text=row['text'],
                    user_draft=row['user_draft'],
                    suggestions=json.loads(row['suggestions_json']),
                    tone=row['tone'],
                    seo_terms=json.loads(row['seo_terms_json']),
                    cta_mode=row['cta_mode'],
                    cta_text=row['cta_text'],
                    cta_intent=row['cta_intent'],
                    destination_url=row['destination_url'],
                    show_price=bool(row['show_price']),
                    price_value=row['price_value'],
                    price_justification=row['price_justification'],
                    price_approved_by=row['price_approved_by'],
                    price_approved_at=row['price_approved_at'],
                    status=row['status'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                )

            copy_id = f"copy-{uuid.uuid4().hex[:12]}"
            now = self._now()
            camp_row = conn.execute('SELECT briefing_json, products_json FROM campaigns WHERE id=?', (campaign_id,)).fetchone()
            briefing = json.loads(camp_row['briefing_json']) if camp_row else {}
            products = json.loads(camp_row['products_json']) if camp_row else []
            first_prod = products[0] if products else {}
            if isinstance(first_prod, dict):
                p_name = first_prod.get('name', 'Vela Aromática')
            elif isinstance(first_prod, str):
                p_name = first_prod
            else:
                p_name = 'Vela Aromática'

            ctx = {
                'product_name': p_name,
                'fragrance': p_name,
                'visual_tone': briefing.get('visual_tone', ''),
            }

            mode = 'user_provided' if initial_caption.strip() else 'automatic'
            user_draft = initial_caption.strip() if mode == 'user_provided' else ''
            text = initial_caption.strip() if mode == 'user_provided' else self.copy_engine.generate_automatic_caption(ctx)
            suggestions = self.copy_engine.generate_caption_suggestions(ctx)

            conn.execute(
                '''INSERT INTO slide_copies (
                    id, campaign_id, slide_id, mode, text, user_draft, suggestions_json, tone,
                    seo_terms_json, cta_mode, cta_text, cta_intent, destination_url, show_price,
                    price_value, price_justification, price_approved_by, price_approved_at, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    copy_id, campaign_id, slide_id, mode, text, user_draft,
                    json.dumps(suggestions, ensure_ascii=False), 'leve, relaxado, brasileiro',
                    json.dumps(['vela aromática', 'cera vegetal'], ensure_ascii=False),
                    'none', '', None, '', 0, None, None, None, None, 'draft', now, now
                ),
            )

            return CaptionContent(
                id=copy_id,
                campaign_id=campaign_id,
                slide_id=slide_id,
                mode=mode,
                text=text,
                user_draft=user_draft,
                suggestions=suggestions,
                tone='leve, relaxado, brasileiro',
                seo_terms=['vela aromática', 'cera vegetal'],
                cta_mode='none',
                cta_text='',
                cta_intent=None,
                destination_url='',
                show_price=False,
                price_value=None,
                price_justification=None,
                price_approved_by=None,
                price_approved_at=None,
                status='draft',
                created_at=now,
                updated_at=now,
            )

    def get_slide_copy(self, slide_id: str) -> Optional[CaptionContent]:
        """Recupera a cópia associada ao slide."""
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM slide_copies WHERE slide_id=?', (slide_id,)).fetchone()
            if not row:
                return None
            return CaptionContent(
                id=row['id'],
                campaign_id=row['campaign_id'],
                slide_id=row['slide_id'],
                mode=row['mode'],
                text=row['text'],
                user_draft=row['user_draft'],
                suggestions=json.loads(row['suggestions_json']),
                tone=row['tone'],
                seo_terms=json.loads(row['seo_terms_json']),
                cta_mode=row['cta_mode'],
                cta_text=row['cta_text'],
                cta_intent=row['cta_intent'],
                destination_url=row['destination_url'],
                show_price=bool(row['show_price']),
                price_value=row['price_value'],
                price_justification=row['price_justification'],
                price_approved_by=row['price_approved_by'],
                price_approved_at=row['price_approved_at'],
                status=row['status'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
            )

    def generate_caption_suggestions_for_slide(self, slide_id: str) -> List[Dict[str, str]]:
        """Gera novas sugestões criativas de legenda para o slide (Seção 35)."""
        current_copy = self.get_slide_copy(slide_id)
        if not current_copy:
            raise ValueError(f"Cópia para o slide '{slide_id}' não encontrada.")
        prod = self.get_product_for_slide(slide_id)
        ctx = {
            'product_name': prod.get('name', 'Vela Aromática'),
            'fragrance': prod.get('name', 'Alecrim & Algodão'),
        }
        suggestions = self.copy_engine.generate_caption_suggestions(ctx)
        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                'UPDATE slide_copies SET suggestions_json=?, updated_at=? WHERE slide_id=?',
                (json.dumps(suggestions, ensure_ascii=False), self._now(), slide_id),
            )
        return suggestions

    def update_slide_copy(
        self,
        slide_id: str,
        mode: str,
        text: Optional[str] = None,
        user_draft: Optional[str] = None,
        cta_mode: Optional[str] = None,
        cta_text: Optional[str] = None,
        cta_intent: Optional[str] = None,
        destination_url: Optional[str] = None,
        show_price: Optional[bool] = None,
        price_justification: Optional[str] = None,
        price_approved_by: Optional[str] = None,
    ) -> CaptionContent:
        """Atualiza a copy do slide com governança estrita de voz, modos e preço (Seções 34-37)."""
        current_copy = self.get_slide_copy(slide_id)
        if not current_copy:
            raise ValueError(f"Cópia para o slide '{slide_id}' não encontrada.")

        prod = self.get_product_for_slide(slide_id)
        ctx = {
            'product_name': prod.get('name', 'Vela Aromática'),
            'fragrance': prod.get('name', 'Alecrim & Algodão'),
        }

        # 1. Determina modo e texto da legenda
        new_mode = mode if mode in VALID_CAPTION_MODES else current_copy.mode
        new_draft = user_draft if user_draft is not None else current_copy.user_draft

        if new_mode == 'user_provided':
            final_text = new_draft if new_draft.strip() else (text or current_copy.text)
        elif new_mode == 'ai_plus_user':
            final_text = self.copy_engine.refine_user_copy(new_draft or text or current_copy.text, ctx)
        elif new_mode == 'automatic':
            final_text = text if text and text != current_copy.text else self.copy_engine.generate_automatic_caption(ctx)
        elif new_mode == 'suggestions':
            final_text = text or current_copy.text
        else:
            final_text = text or current_copy.text

        # 2. CTA contextual
        new_cta_mode = cta_mode if cta_mode in VALID_CTA_MODES else current_copy.cta_mode
        new_cta_intent = cta_intent if cta_intent is not None else current_copy.cta_intent
        if new_cta_mode == 'manual':
            new_cta_text = cta_text or ''
        elif new_cta_mode in ('automatic', 'intent_based'):
            new_cta_text = self.copy_engine.generate_cta(new_cta_mode, intent=new_cta_intent)
        elif new_cta_mode == 'none':
            new_cta_text = ''
        else:
            new_cta_text = cta_text or current_copy.cta_text

        # 3. URL de Destino
        new_dest_url = destination_url if destination_url is not None else current_copy.destination_url

        # 4. Governança de Preço (Seção 37)
        new_show_price = show_price if show_price is not None else current_copy.show_price
        new_price_val = current_copy.price_value
        new_price_just = price_justification if price_justification is not None else current_copy.price_justification
        new_price_appr = price_approved_by if price_approved_by is not None else current_copy.price_approved_by
        new_price_at = current_copy.price_approved_at

        if new_show_price:
            valid, formatted_price = self.copy_engine.validate_and_format_price(
                show_price=True,
                product_data=prod,
                justification=new_price_just,
                approved_by=new_price_appr,
            )
            new_price_val = formatted_price
            if not new_price_at:
                new_price_at = self._now()
        else:
            new_show_price = False
            new_price_val = None

        now = self._now()
        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''UPDATE slide_copies SET
                    mode=?, text=?, user_draft=?, cta_mode=?, cta_text=?, cta_intent=?,
                    destination_url=?, show_price=?, price_value=?, price_justification=?,
                    price_approved_by=?, price_approved_at=?, updated_at=?
                   WHERE slide_id=?''',
                (
                    new_mode, final_text, new_draft, new_cta_mode, new_cta_text, new_cta_intent,
                    new_dest_url, int(new_show_price), new_price_val, new_price_just,
                    new_price_appr, new_price_at, now, slide_id
                ),
            )

        return self.get_slide_copy(slide_id)

    def approve_price_display(
        self,
        slide_id: str,
        justification: str,
        approver: str,
    ) -> CaptionContent:
        """Aprova explicitamente a exibição de preço para um slide (Seção 37)."""
        return self.update_slide_copy(
            slide_id=slide_id,
            mode='automatic',
            show_price=True,
            price_justification=justification,
            price_approved_by=approver,
        )

    # -------------------------------------------------------------
    # Seção 38: Stories e Planejamento de Sequência Próprio
    # -------------------------------------------------------------

    def create_story_sequence(
        self,
        title: str,
        story_type: str = 'independent',
        objective: str = '',
        campaign_id: Optional[str] = None,
    ) -> StorySequence:
        """Planeja e persiste uma sequência narrativa completa de Stories (Seção 38)."""
        ctx = {'campaign_id': campaign_id}
        if campaign_id:
            with sqlite3.connect(self.db.path) as conn:
                conn.row_factory = sqlite3.Row
                c_row = conn.execute('SELECT products_json, briefing_json FROM campaigns WHERE id=?', (campaign_id,)).fetchone()
                if c_row:
                    prods = json.loads(c_row['products_json'])
                    if prods:
                        ctx['product_name'] = prods[0].get('name')
                        ctx['fragrance'] = prods[0].get('name')
                    briefing = json.loads(c_row['briefing_json'])
                    ctx['visual_tone'] = briefing.get('visual_tone')

        seq = self.stories_engine.plan_sequence(
            title=title,
            story_type=story_type,
            objective=objective,
            campaign_context=ctx,
        )

        now = self._now()
        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''INSERT INTO story_sequences (id, campaign_id, title, story_type, objective, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (seq.id, seq.campaign_id, seq.title, seq.story_type, seq.objective, seq.status, now, now),
            )
            for f in seq.frames:
                conn.execute(
                    '''INSERT INTO story_frames (
                        id, sequence_id, frame_order, narrative_role, title, overlay_text, visual_prompt,
                        interaction_type, interaction_data_json, interaction_justification, caption_draft,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        f.id, f.sequence_id, f.frame_order, f.narrative_role, f.title, f.overlay_text,
                        f.visual_prompt, f.interaction_type, json.dumps(f.interaction_data, ensure_ascii=False),
                        f.interaction_justification, f.caption_draft, now, now
                    ),
                )

        return self.get_story_sequence(seq.id)

    def get_story_sequence(self, sequence_id: str) -> Optional[StorySequence]:
        """Recupera sequência de Stories com seus frames."""
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            s_row = conn.execute('SELECT * FROM story_sequences WHERE id=?', (sequence_id,)).fetchone()
            if not s_row:
                return None
            f_rows = conn.execute(
                'SELECT * FROM story_frames WHERE sequence_id=? ORDER BY frame_order ASC',
                (sequence_id,),
            ).fetchall()
            frames = [
                StoryFrame(
                    id=f['id'],
                    sequence_id=f['sequence_id'],
                    frame_order=int(f['frame_order']),
                    narrative_role=f['narrative_role'],
                    title=f['title'],
                    overlay_text=f['overlay_text'],
                    visual_prompt=f['visual_prompt'],
                    interaction_type=f['interaction_type'],
                    interaction_data=json.loads(f['interaction_data_json']),
                    interaction_justification=f['interaction_justification'],
                    caption_draft=f['caption_draft'],
                    created_at=f['created_at'],
                    updated_at=f['updated_at'],
                )
                for f in f_rows
            ]
            return StorySequence(
                id=s_row['id'],
                campaign_id=s_row['campaign_id'],
                title=s_row['title'],
                story_type=s_row['story_type'],
                objective=s_row['objective'],
                frames=frames,
                status=s_row['status'],
                created_at=s_row['created_at'],
                updated_at=s_row['updated_at'],
            )

    def list_story_sequences(self, campaign_id: Optional[str] = None) -> List[StorySequence]:
        """Lista sequências de Stories cadastradas."""
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            if campaign_id:
                rows = conn.execute(
                    'SELECT id FROM story_sequences WHERE campaign_id=? ORDER BY created_at DESC',
                    (campaign_id,),
                ).fetchall()
            else:
                rows = conn.execute('SELECT id FROM story_sequences ORDER BY created_at DESC').fetchall()
            return [self.get_story_sequence(r['id']) for r in rows if self.get_story_sequence(r['id'])]

    def add_story_frame(
        self,
        sequence_id: str,
        narrative_role: str,
        title: str,
        overlay_text: str,
        visual_prompt: str,
        interaction_type: str = 'none',
        interaction_data: Optional[Dict[str, Any]] = None,
        interaction_justification: str = '',
        caption_draft: str = '',
    ) -> StoryFrame:
        """Adiciona um frame à sequência de Stories mantendo a ordenação narrativa."""
        with sqlite3.connect(self.db.path) as conn:
            order_row = conn.execute(
                'SELECT COALESCE(MAX(frame_order), 0) + 1 FROM story_frames WHERE sequence_id=?',
                (sequence_id,),
            ).fetchone()
            order = int(order_row[0])
            frame_id = f"frame-{uuid.uuid4().hex[:12]}"
            now = self._now()
            conn.execute(
                '''INSERT INTO story_frames (
                    id, sequence_id, frame_order, narrative_role, title, overlay_text, visual_prompt,
                    interaction_type, interaction_data_json, interaction_justification, caption_draft,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    frame_id, sequence_id, order, narrative_role, title, overlay_text, visual_prompt,
                    interaction_type, json.dumps(interaction_data or {}, ensure_ascii=False),
                    interaction_justification, caption_draft, now, now
                ),
            )
        seq = self.get_story_sequence(sequence_id)
        for f in seq.frames:
            if f.id == frame_id:
                return f
        raise RuntimeError("Falha ao recuperar frame recém-criado.")

    # -------------------------------------------------------------
    # Auditoria Pré-Publicação (Seções 34-38 e M08-A05)
    # -------------------------------------------------------------

    def audit_slide_pre_publish(self, slide_id: str, operator: str = 'Operador KIROS') -> PrePublishAuditResult:
        """Executa e registra auditoria pré-publicação para o conteúdo do slide."""
        copy_obj = self.get_slide_copy(slide_id)
        if not copy_obj:
            raise ValueError(f"Cópia para o slide '{slide_id}' não encontrada.")
        prod = self.get_product_for_slide(slide_id)
        audit_res = self.pre_publish_auditor.audit_caption(copy_obj, product_data=prod, operator=operator)

        # Registra em pre_publish_audits
        now = self._now()
        audit_id = f"audit-{uuid.uuid4().hex[:12]}"
        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''INSERT INTO pre_publish_audits (id, target_type, target_id, is_ready, checks_json, blocked_reasons_json, operator, created_at)
                   VALUES (?, 'slide_copy', ?, ?, ?, ?, ?, ?)''',
                (
                    audit_id, slide_id, int(audit_res.is_ready),
                    json.dumps([c.to_dict() for c in audit_res.checks], ensure_ascii=False),
                    json.dumps(audit_res.blocked_reasons, ensure_ascii=False),
                    operator, now
                ),
            )
        return audit_res

    def audit_story_sequence_pre_publish(self, sequence_id: str, operator: str = 'Operador KIROS') -> PrePublishAuditResult:
        """Executa e registra auditoria pré-publicação para uma sequência de Stories."""
        seq = self.get_story_sequence(sequence_id)
        if not seq:
            raise ValueError(f"Sequência de Stories '{sequence_id}' não encontrada.")
        audit_res = self.pre_publish_auditor.audit_story_sequence(seq, operator=operator)

        now = self._now()
        audit_id = f"audit-{uuid.uuid4().hex[:12]}"
        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''INSERT INTO pre_publish_audits (id, target_type, target_id, is_ready, checks_json, blocked_reasons_json, operator, created_at)
                   VALUES (?, 'story_sequence', ?, ?, ?, ?, ?, ?)''',
                (
                    audit_id, sequence_id, int(audit_res.is_ready),
                    json.dumps([c.to_dict() for c in audit_res.checks], ensure_ascii=False),
                    json.dumps(audit_res.blocked_reasons, ensure_ascii=False),
                    operator, now
                ),
            )
        return audit_res

    def audit_campaign_pre_publish(self, campaign_id: str, operator: str = 'Operador KIROS') -> Dict[str, Any]:
        """Audita todos os slides e stories vinculados à campanha antes da publicação."""
        camp = self.get_campaign(campaign_id)
        slide_audits = []
        is_campaign_ready = True
        all_blocked_reasons = []

        for s in camp.slides:
            s_audit = self.audit_slide_pre_publish(s.id, operator=operator)
            slide_audits.append(s_audit)
            if not s_audit.is_ready:
                is_campaign_ready = False
                all_blocked_reasons.extend(s_audit.blocked_reasons)

        stories = self.list_story_sequences(campaign_id=campaign_id)
        story_audits = []
        for st in stories:
            st_audit = self.audit_story_sequence_pre_publish(st.id, operator=operator)
            story_audits.append(st_audit)
            if not st_audit.is_ready:
                is_campaign_ready = False
                all_blocked_reasons.extend(st_audit.blocked_reasons)

        return {
            'campaign_id': campaign_id,
            'is_ready': is_campaign_ready,
            'slide_audits': [a.to_dict() for a in slide_audits],
            'story_audits': [a.to_dict() for a in story_audits],
            'blocked_reasons': all_blocked_reasons,
        }


