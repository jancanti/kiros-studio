"""Módulo de Fila, Execução e Recuperação (M05)."""
from kiros.execution.diagnostics import analyze_execution_failure
from kiros.execution.models import (
    CancellationImpact,
    ExecutionJob,
    ExecutionVersion,
    FailureDiagnostic,
    JobExecutionError,
    QueueError,
    RateLimitExceededError,
    UncertainJobError,
    VALID_JOB_STATUSES,
    VALID_MONITORING_MODES,
)
from kiros.execution.queue import ExecutionQueue
from kiros.execution.worker import ExecutionWorker, WorkerPool

__all__ = [
    'ExecutionQueue',
    'ExecutionWorker',
    'WorkerPool',
    'ExecutionJob',
    'ExecutionVersion',
    'FailureDiagnostic',
    'CancellationImpact',
    'QueueError',
    'JobExecutionError',
    'RateLimitExceededError',
    'UncertainJobError',
    'VALID_JOB_STATUSES',
    'VALID_MONITORING_MODES',
    'analyze_execution_failure',
]

