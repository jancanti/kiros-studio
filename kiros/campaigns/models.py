"""Modelos e contratos de Campanha, Storyboard, Pipeline e Aprovação (Seções 10, 23, 31, 56, 66, 75)."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


VALID_CAMPAIGN_STATES = (
    'draft',
    'awaiting_approval',
    'approved',
    'queued',
    'running',
    'validating',
    'completed',
    'failed',
    'paused',
    'cancelled',
    'archived',
)

VALID_APPROVAL_MODES = (
    'minimal',
    'step_by_step',
    'full_control',
)

VALID_STEP_TYPES = (
    'generation',
    'product_integration',
    'harmonization',
    'layout',
)

VALID_FRAMINGS = (
    'wide',
    'medium',
    'close-up',
    'detail',
    'overhead',
)


class UnapprovedExecutionError(RuntimeError):
    """Lançado quando uma campanha tenta ser enfileirada ou executada sem aprovação válida."""
    pass


class InvalidStateTransitionError(ValueError):
    """Lançado quando uma transição de estado da campanha é inválida."""
    pass


class InvalidApprovalError(ValueError):
    """Lançado quando uma operação de aprovação é inválida ou incompatível com o modo configurado."""
    pass


@dataclass
class StoryboardSlide:
    id: str
    campaign_id: str
    slide_order: int
    title: str
    visual_prompt: str
    framing: str = 'medium'
    caption_draft: str = ''
    engine_override: Optional[str] = None
    status: str = 'draft'
    created_at: str = ''
    updated_at: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'campaign_id': self.campaign_id,
            'slide_order': self.slide_order,
            'title': self.title,
            'visual_prompt': self.visual_prompt,
            'framing': self.framing,
            'caption_draft': self.caption_draft,
            'engine_override': self.engine_override,
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }


@dataclass
class PipelineStep:
    id: str
    campaign_id: str
    slide_id: Optional[str]
    step_order: int
    step_type: str
    name: str
    provider_id: str
    model_id: str
    params: Dict[str, Any] = field(default_factory=dict)
    estimated_cost: float = 0.0
    status: str = 'draft'
    created_at: str = ''
    updated_at: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'campaign_id': self.campaign_id,
            'slide_id': self.slide_id,
            'step_order': self.step_order,
            'step_type': self.step_type,
            'name': self.name,
            'provider_id': self.provider_id,
            'model_id': self.model_id,
            'params': self.params,
            'estimated_cost': round(self.estimated_cost, 4),
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }


@dataclass
class CampaignApproval:
    id: str
    campaign_id: str
    step_id: Optional[str]
    plan_version: int
    approved_by: str
    approved_at: str
    estimated_cost: float
    budget_reservation_id: Optional[str] = None
    is_valid: bool = True
    invalidation_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'campaign_id': self.campaign_id,
            'step_id': self.step_id,
            'plan_version': self.plan_version,
            'approved_by': self.approved_by,
            'approved_at': self.approved_at,
            'estimated_cost': round(self.estimated_cost, 4),
            'budget_reservation_id': self.budget_reservation_id,
            'is_valid': self.is_valid,
            'invalidation_reason': self.invalidation_reason,
        }


@dataclass
class Campaign:
    id: str
    title: str
    briefing: Dict[str, Any]
    strategy: Dict[str, Any]
    products: List[Dict[str, Any]]
    approval_mode: str = 'minimal'
    status: str = 'draft'
    plan_version: int = 1
    approved_version: Optional[int] = None
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    budget_limit: Optional[float] = None
    created_at: str = ''
    updated_at: str = ''
    provenance: str = 'user'
    slides: List[StoryboardSlide] = field(default_factory=list)
    pipeline_steps: List[PipelineStep] = field(default_factory=list)
    approvals: List[CampaignApproval] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'briefing': self.briefing,
            'strategy': self.strategy,
            'products': self.products,
            'approval_mode': self.approval_mode,
            'status': self.status,
            'plan_version': self.plan_version,
            'approved_version': self.approved_version,
            'approved_at': self.approved_at,
            'approved_by': self.approved_by,
            'budget_limit': self.budget_limit,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'provenance': self.provenance,
            'slides': [s.to_dict() for s in self.slides],
            'pipeline_steps': [p.to_dict() for p in self.pipeline_steps],
            'approvals': [a.to_dict() for a in self.approvals],
        }
