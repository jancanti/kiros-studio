"""Modelos de dados e contratos para Fila de Execução, Monitoramento e Diagnóstico (M05)."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


VALID_JOB_STATUSES = (
    'pending',
    'running',
    'completed',
    'failed',
    'paused',
    'cancelled',
    'uncertain',
)

VALID_MONITORING_MODES = (
    'quick',
    'supervised',
    'detailed',
    'manual',
)


class QueueError(Exception):
    """Erro base para operações da fila de execução."""
    pass


class JobExecutionError(QueueError):
    """Erro durante a execução de uma etapa do pipeline."""
    pass


class RateLimitExceededError(QueueError):
    """Erro quando o rate limit do provedor foi atingido."""
    pass


class UncertainJobError(QueueError):
    """Lançado quando o resultado de uma requisição é incerto (ex: timeout de rede)."""
    pass


@dataclass
class FailureDiagnostic:
    """Diagnóstico detalhado de falha estruturado conforme a Seção 69 da especificação."""
    provider: str
    step: str
    probable_cause: str
    suggested_fix: str
    potential_cost: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'provider': self.provider,
            'step': self.step,
            'probable_cause': self.probable_cause,
            'suggested_fix': self.suggested_fix,
            'potential_cost': round(self.potential_cost, 4),
        }


@dataclass
class CancellationImpact:
    """Demonstrativo de impacto financeiro e risco de cobrança (Seção 52)."""
    campaign_id: str
    completed_cost: float
    in_flight_risk: float
    cancellable_budget: float
    total_estimated: float
    preserved_versions_count: int
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'campaign_id': self.campaign_id,
            'completed_cost': round(self.completed_cost, 4),
            'in_flight_risk': round(self.in_flight_risk, 4),
            'cancellable_budget': round(self.cancellable_budget, 4),
            'total_estimated': round(self.total_estimated, 4),
            'preserved_versions_count': self.preserved_versions_count,
            'message': self.message,
        }


@dataclass
class ExecutionJob:
    """Trabalho individual da fila de execução vinculado a uma etapa do pipeline."""
    id: str
    campaign_id: str
    step_id: str
    idempotency_key: str
    status: str
    priority: int
    attempt: int
    max_retries: int
    timeout_seconds: float
    provider_id: str
    model_id: str
    prompt: str
    params: Dict[str, Any] = field(default_factory=dict)
    slide_id: Optional[str] = None
    estimated_cost: float = 0.0
    actual_cost: float = 0.0
    budget_reservation_id: Optional[str] = None
    output_asset_id: Optional[str] = None
    output_data: Dict[str, Any] = field(default_factory=dict)
    diagnostic: Optional[FailureDiagnostic] = None
    uncertain_resolution: Optional[str] = None
    locked_by: Optional[str] = None
    locked_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str = ''
    updated_at: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'campaign_id': self.campaign_id,
            'slide_id': self.slide_id,
            'step_id': self.step_id,
            'idempotency_key': self.idempotency_key,
            'status': self.status,
            'priority': self.priority,
            'attempt': self.attempt,
            'max_retries': self.max_retries,
            'timeout_seconds': self.timeout_seconds,
            'provider_id': self.provider_id,
            'model_id': self.model_id,
            'prompt': self.prompt,
            'params': self.params,
            'estimated_cost': self.estimated_cost,
            'actual_cost': self.actual_cost,
            'budget_reservation_id': self.budget_reservation_id,
            'output_asset_id': self.output_asset_id,
            'output_data': self.output_data,
            'diagnostic': self.diagnostic.to_dict() if self.diagnostic else None,
            'uncertain_resolution': self.uncertain_resolution,
            'locked_by': self.locked_by,
            'locked_at': self.locked_at,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }


@dataclass
class ExecutionVersion:
    """Versão de geração preservada de um slide (Seções 51, 52, 53)."""
    id: str
    campaign_id: str
    slide_id: str
    step_id: str
    version_number: int
    provider_id: str
    model_id: str
    prompt: str
    asset_id: Optional[str] = None
    actual_cost: float = 0.0
    status: str = 'completed'
    job_id: Optional[str] = None
    created_at: str = ''

