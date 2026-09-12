"""Modelos e contratos de dados para checagem de fidelidade de produto e versionamento (M06)."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


VALID_FIDELITY_MODES = (
    'recommend_before_spend',  # Padrão da Seção 27: sugere correção e pede aprovação antes de gastar
    'warn_only',               # Apenas alerta o usuário sem bloquear
    'auto_regenerate',          # Tenta regenerar automaticamente sujeito a orçamento e limite de retries
)

VALID_FIDELITY_STATUSES = (
    'passed',
    'warn',
    'failed',
)

VALID_FIDELITY_APPROVAL_STATUSES = (
    'none',
    'pending',
    'approved',
    'rejected',
    'auto_applied',
)

FIDELITY_DIMENSIONS = (
    'shape',
    'proportion',
    'cap',
    'label',
    'logo',
    'colors',
    'material',
    'critical_attributes',
)


@dataclass
class FidelityDiscrepancy:
    """Discrepância detectada em um atributo ou dimensão física do produto."""
    dimension: str
    attribute: str
    expected: str
    detected: str
    severity: str  # 'critical', 'protected', 'free'
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'dimension': self.dimension,
            'attribute': self.attribute,
            'expected': self.expected,
            'detected': self.detected,
            'severity': self.severity,
            'explanation': self.explanation,
        }


@dataclass
class FidelityDimensionResult:
    """Resultado da checagem para uma das 8 dimensões de fidelidade da Seção 27."""
    dimension: str
    score: float
    weight: float
    status: str  # 'match', 'divergent', 'missing'
    discrepancies: List[FidelityDiscrepancy] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'dimension': self.dimension,
            'score': round(self.score, 1),
            'weight': self.weight,
            'status': self.status,
            'discrepancies': [d.to_dict() for d in self.discrepancies],
        }


@dataclass
class FidelityCheckResult:
    """Resultado consolidado da checagem de fidelidade do produto (Seções 27, 78)."""
    id: str
    campaign_id: str
    product_id: str
    asset_id: str
    score: float
    threshold: float
    mode: str
    status: str
    passed: bool
    dimensions: Dict[str, FidelityDimensionResult] = field(default_factory=dict)
    discrepancies: List[FidelityDiscrepancy] = field(default_factory=list)
    suggested_fix: Optional[str] = None
    estimated_correction_cost: float = 0.0
    approval_status: str = 'none'
    slide_id: Optional[str] = None
    version_id: Optional[str] = None
    is_estimated: bool = True
    created_at: str = ''

    @property
    def formatted_score(self) -> str:
        """Formato explícito da Seção 27: 'Fidelidade: 94/100'."""
        return f"Fidelidade: {int(round(self.score))}/100"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'campaign_id': self.campaign_id,
            'slide_id': self.slide_id,
            'version_id': self.version_id,
            'product_id': self.product_id,
            'asset_id': self.asset_id,
            'score': round(self.score, 1),
            'formatted_score': self.formatted_score,
            'threshold': round(self.threshold, 1),
            'mode': self.mode,
            'status': self.status,
            'passed': self.passed,
            'is_estimated': self.is_estimated,
            'dimensions': {k: v.to_dict() for k, v in self.dimensions.items()},
            'discrepancies': [d.to_dict() for d in self.discrepancies],
            'suggested_fix': self.suggested_fix,
            'estimated_correction_cost': round(self.estimated_correction_cost, 4),
            'approval_status': self.approval_status,
            'created_at': self.created_at,
            'disclaimer': 'O score é uma estimativa de visão computacional, não uma prova absoluta.',
        }


@dataclass
class VersionComparison:
    """Comparação lado a lado de até 3 versões de um slide (Seção 54)."""
    slide_id: str
    versions: List[Dict[str, Any]]
    differences: Dict[str, Any]
    max_versions_allowed: int = 3

    def to_dict(self) -> Dict[str, Any]:
        return {
            'slide_id': self.slide_id,
            'versions': self.versions,
            'differences': self.differences,
            'max_versions_allowed': self.max_versions_allowed,
        }

