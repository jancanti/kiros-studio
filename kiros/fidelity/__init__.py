"""Módulo de checagem de fidelidade de produto, versionamento e comparação visual (M06)."""
from kiros.fidelity.models import (
    FIDELITY_DIMENSIONS,
    VALID_FIDELITY_APPROVAL_STATUSES,
    VALID_FIDELITY_MODES,
    VALID_FIDELITY_STATUSES,
    FidelityCheckResult,
    FidelityDimensionResult,
    FidelityDiscrepancy,
    VersionComparison,
)
from kiros.fidelity.service import ProductFidelityService

__all__ = [
    'FIDELITY_DIMENSIONS',
    'VALID_FIDELITY_MODES',
    'VALID_FIDELITY_STATUSES',
    'VALID_FIDELITY_APPROVAL_STATUSES',
    'FidelityDiscrepancy',
    'FidelityDimensionResult',
    'FidelityCheckResult',
    'VersionComparison',
    'ProductFidelityService',
]

