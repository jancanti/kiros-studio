"""Worker de execução e pool concorrente para processamento de etapas do pipeline (M05)."""
import concurrent.futures
import hashlib
import json
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import uuid

from kiros.execution.models import ExecutionJob, UncertainJobError
from kiros.execution.queue import ExecutionQueue
from kiros.infrastructure.local import FileStorage
from kiros.providers.manager import ProviderManager


logger = logging.getLogger(__name__)


class ExecutionWorker:
    """Worker responsável por reivindicar e executar trabalhos da fila com timeout, tratamento de erros e integridade."""

    def __init__(
        self,
        queue: ExecutionQueue,
        provider_manager: Optional[ProviderManager] = None,
        storage: Optional[FileStorage] = None,
        mock_generator: Optional[Callable[[ExecutionJob], Tuple[str, float, Dict[str, Any]]]] = None,
    ):
        self.queue = queue
        self.provider_manager = provider_manager
        self.storage = storage
        self.mock_generator = mock_generator

    def _default_mock_generator(self, job: ExecutionJob) -> Tuple[str, float, Dict[str, Any]]:
        """Gera asset simulado determinístico para ambiente local/mock sem tráfego de rede."""
        content = f"KIROS_IMAGE_ASSET:{job.provider_id}:{job.model_id}:{job.prompt}:{job.attempt}".encode('utf-8')
        asset_hash = hashlib.sha256(content).hexdigest()
        asset_id = f"asset-{asset_hash[:16]}.png"

        if self.storage:
            self.storage.put(f"generated/{asset_id}", content)

        actual_cost = float(job.estimated_cost or 0.16)
        output_data = {
            'dimensions': {'width': 1024, 'height': 1024},
            'format': 'png',
            'simulated': True,
            'provider': job.provider_id,
            'model': job.model_id,
        }
        return asset_id, actual_cost, output_data

    def execute_job(self, job: ExecutionJob) -> ExecutionJob:
        """Executa um trabalho individual, respeitando timeout e registrando sucesso, falha ou incerteza (M05-A01, M05-A03)."""
        timeout = float(job.timeout_seconds or 30.0)

        # Executa a geração sob proteção de timeout
        def target_execution():
            if self.mock_generator:
                return self.mock_generator(job)
            return self._default_mock_generator(job)

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(target_execution)
            try:
                asset_id, actual_cost, output_data = future.result(timeout=timeout)
                # Conclusão com sucesso
                return self.queue.record_job_success(
                    job_id=job.id,
                    output_asset_id=asset_id,
                    actual_cost=actual_cost,
                    output_data=output_data,
                )
            except concurrent.futures.TimeoutError:
                # Timeout de requisição: marca como incerto para não cobrar nem reexecutar cegamente (M05-A03)
                return self.queue.record_job_uncertain(
                    job_id=job.id,
                    error_message=f"Tempo limite de {timeout}s excedido durante a requisição com o provedor {job.provider_id}.",
                )
            except Exception as exc:
                # Falha com diagnóstico estruturado e política finita de retries (M05-A01, M05-A04)
                return self.queue.record_job_failure(
                    job_id=job.id,
                    error_message=str(exc),
                    retry_allowed=True,
                )

    def run_once(self, worker_id: Optional[str] = None) -> Optional[ExecutionJob]:
        """Reivindica e executa um trabalho da fila. Retorna o trabalho concluído/atualizado ou None se vazia."""
        wid = worker_id or f"worker-{threading.get_ident()}-{uuid.uuid4().hex[:6]}"
        job = self.queue.claim_next_job(worker_id=wid)
        if not job:
            return None
        return self.execute_job(job)

    def run_all_pending(self, max_cycles: int = 100) -> int:
        """Executa todos os trabalhos pendentes sequencialmente até esgotar a fila ou atingir o limite de ciclos."""
        cycles = 0
        while cycles < max_cycles:
            job = self.run_once()
            if not job:
                break
            cycles += 1
        return cycles


class WorkerPool:
    """Pool de workers para execução com controle estrito de concorrência e thread-safety (M05-A01, M05-A05)."""

    def __init__(
        self,
        queue: ExecutionQueue,
        max_concurrency: int = 2,
        provider_manager: Optional[ProviderManager] = None,
        storage: Optional[FileStorage] = None,
        mock_generator: Optional[Callable[[ExecutionJob], Tuple[str, float, Dict[str, Any]]]] = None,
    ):
        self.queue = queue
        self.max_concurrency = max(1, max_concurrency)
        self.provider_manager = provider_manager
        self.storage = storage
        self.mock_generator = mock_generator

    def run_concurrent(self, max_cycles: int = 50) -> int:
        """Executa trabalhos pendentes concorrentemente respeitando max_concurrency."""
        completed_count = 0
        lock = threading.Lock()

        def worker_loop(thread_index: int):
            nonlocal completed_count
            worker = ExecutionWorker(
                self.queue,
                self.provider_manager,
                self.storage,
                self.mock_generator,
            )
            wid = f"pool-worker-{thread_index}"
            local_count = 0

            while local_count < max_cycles:
                job = worker.run_once(worker_id=wid)
                if not job:
                    break
                with lock:
                    completed_count += 1
                local_count += 1

        threads = []
        for i in range(self.max_concurrency):
            t = threading.Thread(target=worker_loop, args=(i,), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30.0)

        return completed_count
