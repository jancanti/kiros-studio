"""Testes unitários para CostManager, controle de gastos e reservas concorrentes (M02-A05)."""
from pathlib import Path
import tempfile
import threading
import unittest

from kiros.application import Application
from kiros.core.contracts import Provenance
from kiros.cost import BudgetExceededError, CostManager, UnknownPricingError


class CostManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = Application(Path(self.tmp.name))
        self.cm = self.app.cost_manager

    def provenance(self, ref='teste-custo'):
        return Provenance('user', ref, '2026-09-12T12:00:00+00:00')

    def test_estimated_vs_actual_cost_separation(self):
        # M02-A05: CostManager separa estimativa de custo real e registra campanha/asset/etapa
        cid = 'camp-custo-sep'
        self.cm.set_campaign_budget(cid, limit=1.00, alert_threshold=0.8, provenance=self.provenance())

        # Registra gasto onde a estimativa é diferente do custo real final
        self.cm.record_direct_spend(
            campaign_id=cid,
            asset_id='asset-001',
            stage='environment_generation',
            provider='gemini',
            model='imagen-3.0-generate-002',
            estimated_cost=0.030,
            actual_cost=0.032,  # Pequena variação real
            generation_count=1,
            provenance=self.provenance(),
        )

        summary = self.cm.get_cost_summary(cid)
        self.assertEqual(summary['estimated_total'], 0.030)
        self.assertEqual(summary['actual_total'], 0.032)
        self.assertEqual(summary['generations_count'], 1)
        self.assertEqual(len(summary['records']), 1)

        rec = summary['records'][0]
        self.assertEqual(rec['asset_id'], 'asset-001')
        self.assertEqual(rec['stage'], 'environment_generation')
        self.assertEqual(rec['provider'], 'gemini')
        self.assertEqual(rec['model'], 'imagen-3.0-generate-002')
        self.assertEqual(rec['estimated_cost'], 0.030)
        self.assertEqual(rec['actual_cost'], 0.032)
        self.assertIn('T', rec['timestamp'])

    def test_budget_limits_and_alert_thresholds(self):
        cid = 'camp-budget-alert'
        self.cm.set_campaign_budget(cid, limit=0.10, alert_threshold=0.75, provenance=self.provenance())

        summary = self.cm.get_cost_summary(cid)
        self.assertFalse(summary['is_alert_triggered'])
        self.assertFalse(summary['is_exceeded'])

        # Gasta 0.06 -> 60% (abaixo do alerta de 75%)
        self.cm.record_direct_spend(cid, 'a1', 'gen', 'gemini', 'imagen-3.0-generate-002', 0.06, 0.06)
        summary = self.cm.get_cost_summary(cid)
        self.assertFalse(summary['is_alert_triggered'])
        self.assertFalse(summary['is_exceeded'])

        # Gasta mais 0.02 -> 80% (dispara alerta de 75%)
        self.cm.record_direct_spend(cid, 'a2', 'gen', 'gemini', 'imagen-3.0-generate-002', 0.02, 0.02)
        summary = self.cm.get_cost_summary(cid)
        self.assertTrue(summary['is_alert_triggered'])
        self.assertFalse(summary['is_exceeded'])

        # Gasta mais 0.03 -> 110% (excede limite de 0.10)
        self.cm.record_direct_spend(cid, 'a3', 'gen', 'gemini', 'imagen-3.0-generate-002', 0.03, 0.03)
        summary = self.cm.get_cost_summary(cid)
        self.assertTrue(summary['is_exceeded'])

    def test_plan_action_before_expensive_operations(self):
        # M02-A05: Plano, Custo, Impacto, Confiança, Alternativas, Aprovação
        cid = 'camp-plan'
        self.cm.set_campaign_budget(cid, limit=0.08, alert_threshold=0.8, provenance=self.provenance())

        plan = self.cm.plan_action(
            campaign_id=cid,
            stages=['scene_layout', 'image_generation', 'product_integration'],
            provider='openai',
            model='dall-e-3',
            count=2,  # 2 * 0.040 = 0.080
        )

        self.assertEqual(plan['cost'], 0.080)
        self.assertEqual(plan['plan']['stages'], ['scene_layout', 'image_generation', 'product_integration'])
        self.assertEqual(plan['plan']['generations_count'], 2)
        self.assertGreater(plan['confidence'], 0.8)
        self.assertIn('after_action_total', plan['impact'])
        self.assertTrue(plan['impact']['triggers_alert'])
        self.assertFalse(plan['impact']['exceeds_budget'])
        self.assertGreater(len(plan['alternatives']), 0)

        # Tentativa de gerar 3 imagens (0.120) excede o orçamento de 0.080 e exige autorização
        plan_expensive = self.cm.plan_action(cid, ['gen'], 'openai', 'dall-e-3', count=3)
        self.assertTrue(plan_expensive['impact']['exceeds_budget'])
        self.assertTrue(plan_expensive['requires_authorization'])

    def test_budget_reservation_and_concurrency(self):
        # M02-A05: Reserva orçamento antes da execução concorrente; limites exigem autorização
        cid = 'camp-concurrency'
        self.cm.set_campaign_budget(cid, limit=0.09, provenance=self.provenance())

        # Reserva 1: 0.040 (sucesso)
        r1 = self.cm.reserve_budget(cid, 0.040)
        self.assertTrue(r1)
        self.assertEqual(self.cm.get_cost_summary(cid)['reserved_total'], 0.040)

        # Reserva 2: 0.040 (total 0.080 <= 0.090, sucesso)
        r2 = self.cm.reserve_budget(cid, 0.040)
        self.assertTrue(r2)
        self.assertEqual(self.cm.get_cost_summary(cid)['reserved_total'], 0.080)

        # Reserva 3: 0.040 (total seria 0.120 > 0.090) sem aprovação deve ser recusada
        with self.assertRaises(BudgetExceededError):
            self.cm.reserve_budget(cid, 0.040, approved=False)

        # Com aprovação explícita, a reserva acima do limite é permitida
        r3 = self.cm.reserve_budget(cid, 0.040, approved=True)
        self.assertTrue(r3)
        self.assertEqual(self.cm.get_cost_summary(cid)['reserved_total'], 0.120)

        # Conclusão (commit) da reserva 1 com custo real
        self.cm.commit_reservation(
            reservation_id=r1,
            actual_cost=0.038,
            asset_id='asset-100',
            stage='generation',
            provider='gemini',
            model='imagen-3.0-generate-002',
            provenance=self.provenance(),
        )
        summary = self.cm.get_cost_summary(cid)
        self.assertEqual(summary['actual_total'], 0.038)
        self.assertEqual(summary['reserved_total'], 0.080)  # r2 e r3 continuam reservados

        # Liberação (release) da reserva r3 (cancelamento)
        self.cm.release_reservation(r3)
        summary = self.cm.get_cost_summary(cid)
        self.assertEqual(summary['reserved_total'], 0.040)  # apenas r2

    def test_concurrent_reservations_thread_safety(self):
        # Múltiplas threads tentando reservar simultaneamente dentro do limite
        cid = 'camp-threads'
        # Limite comporta exatamente 5 reservas de 0.010
        self.cm.set_campaign_budget(cid, limit=0.050, provenance=self.provenance())

        results = {'success': 0, 'blocked': 0}
        lock = threading.Lock()

        def try_reserve():
            try:
                self.cm.reserve_budget(cid, 0.010, approved=False)
                with lock:
                    results['success'] += 1
            except BudgetExceededError:
                with lock:
                    results['blocked'] += 1

        threads = [threading.Thread(target=try_reserve) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exatamente 5 devem ter sucesso e 5 bloqueadas
        self.assertEqual(results['success'], 5)
        self.assertEqual(results['blocked'], 5)
        self.assertEqual(self.cm.get_cost_summary(cid)['reserved_total'], 0.050)

    def test_unknown_price_rejects_spend(self):
        # M02-A06: falha ou preço desconhecido não autoriza gasto
        with self.assertRaises(UnknownPricingError):
            self.cm.estimate_cost('custom', 'unregistered-model')


if __name__ == '__main__':
    unittest.main()

