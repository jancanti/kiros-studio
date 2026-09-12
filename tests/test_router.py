"""Testes unitários para o Image Engine Router (M02-A04)."""
from pathlib import Path
import tempfile
import unittest

from kiros.application import Application
from kiros.core.contracts import Provenance
from kiros.providers.router import ImageEngineRouter


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = Application(Path(self.tmp.name))
        self.router = self.app.router

    def provenance(self, ref='teste-roteador'):
        return Provenance('user', ref, '2026-09-12T12:00:00+00:00')

    def test_automatic_recommendation_structure(self):
        # M02-A04: Recomendação deve conter Provider, Model, Reason, Estimated cost, Confidence, Alternatives
        rec = self.router.recommend({'type': 'ambient'})
        self.assertIn('provider', rec)
        self.assertIn('model', rec)
        self.assertIn('reason', rec)
        self.assertIn('estimated_cost', rec)
        self.assertIn('confidence', rec)
        self.assertIn('alternatives', rec)

        self.assertIsInstance(rec['estimated_cost'], float)
        self.assertGreater(rec['estimated_cost'], 0)
        self.assertGreaterEqual(rec['confidence'], 0.5)
        self.assertGreater(len(rec['alternatives']), 0)
        for alt in rec['alternatives']:
            self.assertIn('provider', alt)
            self.assertIn('model', alt)
            self.assertIn('estimated_cost', alt)
            self.assertIn('confidence', alt)
            self.assertIn('reason', alt)

    def test_recommendation_varies_by_context(self):
        # Cenário conceitual recomenda OpenAI DALL-E 3
        conceptual = self.router.recommend({'type': 'conceptual'})
        self.assertEqual(conceptual['provider'], 'openai')
        self.assertEqual(conceptual['model'], 'dall-e-3')

        # Cenário estúdio / packshot recomenda Firefly
        studio = self.router.recommend({'type': 'studio'})
        self.assertEqual(studio['provider'], 'firefly')
        self.assertEqual(studio['model'], 'firefly-image-3')

        # Prioridade de economia recomenda modelo Fast
        economy = self.router.recommend({'budget_priority': 'economy'})
        self.assertEqual(economy['provider'], 'gemini')
        self.assertEqual(economy['model'], 'imagen-3.0-fast-generate-001')
        self.assertEqual(economy['estimated_cost'], 0.020)

    def test_manual_override_priority(self):
        # M02-A04: manual prevalece
        camp_id = 'camp-natal-2026'

        # 1. Sem configuração: recomendação automática
        res_auto = self.router.resolve(camp_id, slide_index=0, slide_context={'type': 'ambient'})
        self.assertFalse(res_auto['is_manual'])
        self.assertEqual(res_auto['source'], 'automatic_recommendation')

        # 2. Configura default da campanha para Firefly
        self.router.set_campaign_default(camp_id, 'firefly', 'firefly-image-3', self.provenance())
        res_default = self.router.resolve(camp_id, slide_index=0)
        self.assertTrue(res_default['is_manual'])
        self.assertEqual(res_default['source'], 'campaign_default')
        self.assertEqual(res_default['provider'], 'firefly')
        self.assertEqual(res_default['model'], 'firefly-image-3')

        # 3. Slide 2 com override específico para OpenAI
        self.router.set_slide_override(camp_id, 2, 'openai', 'dall-e-3', self.provenance('slide-2-custom'))

        # Slide 0 continua com o default da campanha
        self.assertEqual(self.router.resolve(camp_id, slide_index=0)['provider'], 'firefly')

        # Slide 2 tem override específico e vence o default da campanha
        res_slide = self.router.resolve(camp_id, slide_index=2)
        self.assertTrue(res_slide['is_manual'])
        self.assertEqual(res_slide['source'], 'slide_override')
        self.assertEqual(res_slide['provider'], 'openai')
        self.assertEqual(res_slide['model'], 'dall-e-3')

        # 4. Remover override do slide volta ao default da campanha
        self.router.clear_slide_override(camp_id, 2)
        self.assertEqual(self.router.resolve(camp_id, slide_index=2)['source'], 'campaign_default')

    def test_router_persists_across_reopen(self):
        camp_id = 'camp-persist'
        self.router.set_campaign_default(camp_id, 'gemini', 'imagen-3.0-generate-002', self.provenance())
        self.router.set_slide_override(camp_id, 1, 'openai', 'dall-e-3', self.provenance())

        # Reabre banco
        reopened = Application(Path(self.tmp.name)).router
        routing = reopened.get_campaign_routing(camp_id)
        self.assertIsNotNone(routing)
        self.assertEqual(routing['default_engine'], 'gemini')
        self.assertEqual(routing['default_model'], 'imagen-3.0-generate-002')
        self.assertIn('1', routing['slide_overrides'])
        self.assertEqual(routing['slide_overrides']['1']['engine'], 'openai')


if __name__ == '__main__':
    unittest.main()

