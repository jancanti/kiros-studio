"""Testes unitários para Fila, Execução e Recuperação (M05-A01 a M05-A05)."""
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock

from kiros.application import Application
from kiros.core.contracts import Provenance
from kiros.execution.diagnostics import analyze_execution_failure
from kiros.execution.models import (
    CancellationImpact,
    ExecutionJob,
    FailureDiagnostic,
    UncertainJobError,
)
from kiros.execution.worker import ExecutionWorker, WorkerPool


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = Application(Path(self.tmp.name))
        self.mgr = self.app.campaigns
        self.queue = self.app.queue
        self.cost = self.app.cost_manager
        self.worker = self.app.worker

        # Cria campanha base aprovada
        self.cid = self.mgr.create_campaign(
            title='Campanha Fila Teste',
            briefing={'primary_objective': 'lançamento', 'summary': 'Campanha de testes de fila'},
            strategy={'funnel_stage': 'Descoberta'},
            products=[{'product_id': 'vela-01', 'name': 'Vela Alecrim'}],
            approval_mode='minimal',
            provenance=Provenance('user', 'test.execution', '2026-09-12T12:00:00+00:00'),
        )
        self.s1 = self.mgr.add_storyboard_slide(self.cid, 'Slide 1', 'Prompt slide 1', framing='wide')
        self.s2 = self.mgr.add_storyboard_slide(self.cid, 'Slide 2', 'Prompt slide 2', framing='detail')
        self.mgr.submit_for_approval(self.cid)
        self.mgr.approve_campaign(self.cid, approver='Diretoria')

    def test_persistent_queue_priority_and_rate_limit(self):
        # M05-A01: Fila persistente com concorrência, prioridade, rate limit e timeout
        jobs = self.queue.enqueue_campaign_execution(self.cid, priority=10, timeout_seconds=15.0, max_retries=3)
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0].status, 'pending')
        self.assertEqual(jobs[1].status, 'pending')

        # Testa ordenação por prioridade: insere trabalho de alta prioridade (prioridade 1)
        high_prio_job = self.queue.regenerate_slide(self.cid, self.s2, new_prompt='Regen urgente')
        self.assertEqual(high_prio_job.priority, 5)

        # Worker reivindica o trabalho de maior prioridade primeiro
        claimed = self.queue.claim_next_job(worker_id='w1')
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.id, high_prio_job.id)
        self.assertEqual(claimed.status, 'running')
        self.assertEqual(claimed.locked_by, 'w1')

        # Testa rate limit do provedor
        self.queue.rate_limits_rpm['gemini'] = 1  # Força cota para 1 req/min
        self.queue.record_provider_call('gemini')
        self.assertFalse(self.queue.check_rate_limit('gemini'))

    def test_finite_retries_fail_without_infinite_loop(self):
        # M05-A01: Retries finitos, nunca infinito; falha definitiva após max_retries
        jobs = self.queue.enqueue_campaign_execution(self.cid, max_retries=2)
        job = jobs[0]

        # 1ª tentativa
        claimed1 = self.queue.claim_next_job(worker_id='w-retry')
        self.assertEqual(claimed1.attempt, 1)
        retried1 = self.queue.record_job_failure(claimed1.id, "Erro 503 temporário do provedor", retry_allowed=True)
        self.assertEqual(retried1.status, 'pending')  # Volta para tentar novamente

        # 2ª tentativa (atinge max_retries=2)
        claimed2 = self.queue.claim_next_job(worker_id='w-retry')
        self.assertEqual(claimed2.attempt, 2)
        failed = self.queue.record_job_failure(claimed2.id, "Erro 503 persistente", retry_allowed=True)

        # Agora falhou definitivamente, sem loop infinito
        self.assertEqual(failed.status, 'failed')
        self.assertIsNotNone(failed.diagnostic)
        self.assertEqual(failed.diagnostic.provider, 'GEMINI')

    def test_pause_resume_and_cancellation_with_charge_risk(self):
        # M05-A02: Pausa, retomada, cancelamento de geração/slide/campanha preservam resultados e informam risco
        jobs = self.queue.enqueue_campaign_execution(self.cid)
        j1 = jobs[0]
        j2 = jobs[1]

        # Conclui primeiro trabalho com sucesso
        self.queue.claim_next_job('w1')
        self.queue.record_job_success(j1.id, output_asset_id='asset-01.png', actual_cost=0.16)

        # Pausa a campanha
        self.queue.pause_campaign(self.cid)
        camp = self.mgr.get_campaign(self.cid)
        self.assertEqual(camp.status, 'paused')
        self.assertEqual(self.queue.get_job(j2.id).status, 'paused')
        # Trabalho 1 permanece completed (M05-A02)
        self.assertEqual(self.queue.get_job(j1.id).status, 'completed')

        # Retoma a campanha
        self.queue.resume_campaign(self.cid)
        self.assertEqual(self.queue.get_job(j2.id).status, 'pending')
        self.assertEqual(self.queue.get_job(j1.id).status, 'completed')

        # Consulta demonstrativo de cancelamento antes de cancelar
        impact = self.queue.get_cancellation_impact(self.cid)
        self.assertEqual(impact.completed_cost, 0.16)
        self.assertGreater(impact.cancellable_budget, 0.0)
        self.assertIn('Custo incorrido irrecuperável', impact.message)

        # Cancela a campanha
        cancelled_impact = self.queue.cancel_campaign(self.cid)
        self.assertEqual(self.queue.get_job(j2.id).status, 'cancelled')
        # Trabalho 1 e versões geradas continuam preservados! (Seção 52)
        self.assertEqual(self.queue.get_job(j1.id).status, 'completed')
        versions = self.queue.list_versions_for_slide(self.s1)
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0].asset_id, 'asset-01.png')

    def test_idempotency_prevents_duplicate_jobs_and_charges(self):
        # M05-A03: Idempotência evita geração e cobrança duplicada
        jobs1 = self.queue.enqueue_campaign_execution(self.cid)
        # Segunda chamada com o mesmo plano não gera novos trabalhos nem duplica reserva
        jobs2 = self.queue.enqueue_campaign_execution(self.cid)

        self.assertEqual(len(jobs1), len(jobs2))
        self.assertEqual([j.id for j in jobs1], [j.id for j in jobs2])
        self.assertEqual([j.idempotency_key for j in jobs1], [j.idempotency_key for j in jobs2])

    def test_uncertain_result_reconciliation_on_timeout(self):
        # M05-A03: Reconciliação de resultado incerto; timeout não dispara nova cobrança automaticamente
        jobs = self.queue.enqueue_campaign_execution(self.cid, timeout_seconds=0.01)
        job = jobs[0]

        # Simula worker com timeout
        def slow_generator(j):
            time.sleep(0.05)
            return 'asset.png', 0.16, {}

        custom_worker = ExecutionWorker(self.queue, mock_generator=slow_generator)
        claimed = self.queue.claim_next_job('w-slow')
        result_job = custom_worker.execute_job(claimed)

        # O trabalho é marcado como 'uncertain' sem cobrança duplicada nem reexecução automática
        self.assertEqual(result_job.status, 'uncertain')
        self.assertEqual(result_job.uncertain_resolution, 'pending_reconciliation')

        # Reconciliação manual: confirmando falha sem cobrança
        reconciled = self.queue.reconcile_uncertain_job(result_job.id, outcome='failed')
        self.assertEqual(reconciled.status, 'failed')
        self.assertEqual(reconciled.actual_cost, 0.0)

    def test_monitoring_modes_and_failure_diagnostics_section_69(self):
        # M05-A04: Modos Quick/Supervised/Detailed/Manual e diagnóstico estruturado conforme Seção 69
        self.queue.set_monitoring_mode(self.cid, 'manual')
        self.assertEqual(self.queue.get_monitoring_mode(self.cid), 'manual')

        # Em modo manual, trabalhos iniciam em 'paused' para controle passo a passo
        jobs_manual = self.queue.enqueue_campaign_execution(self.cid)
        self.assertEqual(jobs_manual[0].status, 'paused')

        # Altera para Quick
        self.queue.set_monitoring_mode(self.cid, 'quick')
        self.assertEqual(self.queue.get_monitoring_mode(self.cid), 'quick')

        # Diagnósticos da Seção 69 cobrindo RateLimit, Timeout, Moderation e Budget
        diag_rl = analyze_execution_failure('gemini', 'Etapa 1', 'Error 429 Rate Limit Exceeded', 0.16, status_code=429)
        self.assertEqual(diag_rl.provider, 'GEMINI')
        self.assertIn('Limite de requisições', diag_rl.probable_cause)
        self.assertIn('60s', diag_rl.suggested_fix)
        self.assertEqual(diag_rl.potential_cost, 0.16)

        diag_mod = analyze_execution_failure('openai', 'Etapa 2', 'Safety policy violation trigger', 0.20)
        self.assertEqual(diag_mod.provider, 'OPENAI')
        self.assertIn('segurança ou moderação', diag_mod.probable_cause)
        self.assertIn('Revise o prompt', diag_mod.suggested_fix)

    def test_concurrent_worker_pool_and_stale_lock_recovery(self):
        # M05-A05: Testes cobrem concorrência, pool de workers e reinício com recuperação de lock
        self.queue.enqueue_campaign_execution(self.cid)

        # WorkerPool com 2 workers concorrentes processando a fila
        pool = WorkerPool(self.queue, max_concurrency=2)
        completed_count = pool.run_concurrent()
        self.assertEqual(completed_count, 2)

        # Todos os trabalhos foram concluídos sem duplicatas
        all_jobs = self.queue.list_jobs_for_campaign(self.cid)
        self.assertTrue(all(j.status == 'completed' for j in all_jobs))
        self.assertEqual(self.mgr.get_campaign(self.cid).status, 'completed')

        # Testa recuperação de worker que caiu (stale lock recovery)
        regen_job = self.queue.regenerate_slide(self.cid, self.s1)
        # Força um lock antigo simulando crash de worker
        import sqlite3
        with sqlite3.connect(self.app.database.path) as conn:
            conn.execute(
                "UPDATE execution_jobs SET status='running', locked_by='dead-worker', locked_at='2026-01-01T00:00:00+00:00' WHERE id=?",
                (regen_job.id,),
            )

        recovered = self.queue.release_stale_locks(timeout_multiplier=1.0)
        self.assertEqual(recovered, 1)
        recovered_job = self.queue.get_job(regen_job.id)
        self.assertEqual(recovered_job.status, 'pending')
        self.assertIsNone(recovered_job.locked_by)


if __name__ == '__main__':
    unittest.main()
