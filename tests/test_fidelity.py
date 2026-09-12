"""Testes unitários para Checagem de Fidelidade de Produto, Versionamento e Comparação (M06-A01 a M06-A05)."""
from pathlib import Path
import tempfile
import unittest

from kiros.application import Application
from kiros.core.contracts import Provenance
from kiros.fidelity.fixtures import (
    FIXTURE_ALTERED_LABEL,
    FIXTURE_ALTERED_LOGO,
    FIXTURE_ALTERED_PRODUCT,
    FIXTURE_CORRECT_PRODUCT,
)
from kiros.fidelity.models import FidelityCheckResult


class FidelityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = Application(Path(self.tmp.name))
        self.lib = self.app.library
        self.mgr = self.app.campaigns
        self.queue = self.app.queue
        self.cost = self.app.cost_manager
        self.fidelity = self.app.fidelity_service
        self.worker = self.app.worker

        # 1. Cadastra produto oficial na biblioteca
        self.prod_id = self.lib.create_product('vela-alecrim', 'Vela Aromática Alecrim & Oliva')

        # 2. Adiciona referências visuais reais do produto (Seção 78)
        # Cabeçalho PNG válido de teste (16+ bytes)
        png_sample = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4'
        self.lib.add_reference(
            png_sample,
            product_id=self.prod_id,
            scope='permanent',
            origin='own',
            source_reference='Catálogo Oficial Kiros 2026',
            rights='confirmed',
            angle='front',
            quality=5,
        )
        self.lib.add_reference(
            png_sample,
            product_id=self.prod_id,
            scope='permanent',
            origin='own',
            source_reference='Catálogo Oficial Detalhe',
            rights='confirmed',
            angle='detail',
            quality=4,
        )

        # 3. Propõe e aprova Product Bible com atributos críticos (Seção 27)
        prop_id = self.lib.propose(
            'product',
            self.prod_id,
            {
                'shape': {'value': 'Cilíndrico clássico com base espessa', 'protection': 'protected'},
                'proportion': {'value': '1:1.5 proporção áurea', 'protection': 'protected'},
                'material': {'value': 'Vidro soprado âmbar e cera de coco', 'protection': 'protected'},
                'glass': {'value': 'Vidro âmbar translúcido resistente', 'protection': 'protected'},
                'cap': {'value': 'Tampa de madeira nobre escura torneada', 'protection': 'protected'},
                'label': {'value': 'Papel linho branco com tipografia preta serifada', 'protection': 'critical'},
                'logo': {'value': 'Monograma Kiros dourado na parte superior frontal', 'protection': 'critical'},
                'colors': {'value': 'Âmbar, madeira escura e bege linho', 'protection': 'protected'},
                'packaging': {'value': 'Cartucho rígido kraft texturizado', 'protection': 'free'},
            },
            source='Especificação Técnica de Produto',
        )
        self.lib.approve(prop_id, approver='Diretor de Produto')

        # 4. Cria campanha de teste aprovada
        self.cid = self.mgr.create_campaign(
            title='Campanha Fidelidade M06',
            briefing={'primary_objective': 'lançamento', 'summary': 'Campanha de validação de fidelidade'},
            strategy={'funnel_stage': 'Descoberta'},
            products=[{'product_id': self.prod_id, 'name': 'Vela Aromática Alecrim & Oliva'}],
            approval_mode='minimal',
            provenance=Provenance('user', 'test.fidelity', '2026-09-12T12:00:00+00:00'),
        )
        self.s1 = self.mgr.add_storyboard_slide(self.cid, 'Slide 1 - Frasco Frontal', 'Prompt detalhado frontal', framing='medium')
        self.mgr.submit_for_approval(self.cid)
        self.mgr.approve_campaign(self.cid, approver='Diretoria')

    def test_fidelity_check_uses_real_references_and_critical_attributes(self):
        # M06-A01: Fidelity Check usa referência real e atributos críticos; score estimado, threshold configurável, recommend_before_spend padrão
        # Verifica configuração padrão
        cfg = self.fidelity.get_campaign_fidelity_config(self.cid)
        self.assertEqual(cfg['mode'], 'recommend_before_spend')
        self.assertEqual(cfg['threshold'], 85.0)

        # Executa checagem de fidelidade
        result = self.fidelity.check_fidelity(
            campaign_id=self.cid,
            product_id=self.prod_id,
            asset_id='asset-test-01.png',
            slide_id=self.s1,
            fixture_override=FIXTURE_CORRECT_PRODUCT,
        )

        self.assertIsInstance(result, FidelityCheckResult)
        self.assertTrue(result.passed)
        self.assertEqual(result.status, 'passed')
        self.assertEqual(result.formatted_score, 'Fidelidade: 94/100')
        self.assertTrue(result.is_estimated)  # Explicitamente estimado conforme Seção 27
        self.assertEqual(result.mode, 'recommend_before_spend')

        # Verifica as 8 dimensões obrigatórias da Seção 27
        expected_dims = {'shape', 'proportion', 'cap', 'label', 'logo', 'colors', 'material', 'critical_attributes'}
        self.assertEqual(set(result.dimensions.keys()), expected_dims)
        self.assertEqual(result.dimensions['logo'].status, 'match')
        self.assertEqual(result.dimensions['label'].status, 'match')

        # Verifica threshold configurável
        self.fidelity.set_campaign_fidelity_config(self.cid, mode='recommend_before_spend', threshold=96.0)
        cfg_updated = self.fidelity.get_campaign_fidelity_config(self.cid)
        self.assertEqual(cfg_updated['threshold'], 96.0)

        # Com threshold 96.0, score 94.0 agora falha no limite
        result_strict = self.fidelity.check_fidelity(
            campaign_id=self.cid,
            product_id=self.prod_id,
            asset_id='asset-test-01.png',
            slide_id=self.s1,
            fixture_override=FIXTURE_CORRECT_PRODUCT,
        )
        self.assertFalse(result_strict.passed)
        self.assertEqual(result_strict.status, 'failed')

    def test_fidelity_failure_explains_differences_suggests_fix_estimates_cost_and_respects_approval(self):
        # M06-A02: Falha explica diferenças, sugere correção, estima custo e respeita aprovação; auto_regenerate sujeito a orçamento e retries
        result = self.fidelity.check_fidelity(
            campaign_id=self.cid,
            product_id=self.prod_id,
            asset_id='asset-altered-logo.png',
            slide_id=self.s1,
            fixture_override=FIXTURE_ALTERED_LOGO,
            mode_override='recommend_before_spend',
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.status, 'failed')

        # 1. Explica diferenças estruturadas
        self.assertGreater(len(result.discrepancies), 0)
        logo_disc = next(d for d in result.discrepancies if d.attribute == 'logo')
        self.assertEqual(logo_disc.severity, 'critical')
        self.assertIn('Monograma oficial da marca ausente', logo_disc.explanation)

        # 2. Sugere correção prescritiva
        self.assertIsNotNone(result.suggested_fix)
        self.assertIn('logotipo oficial', result.suggested_fix.lower())

        # 3. Estima custo da regeneração corretiva
        self.assertGreater(result.estimated_correction_cost, 0.0)

        # 4. Respeita aprovação no modo recommend_before_spend (não gasta sem aprovação)
        self.assertEqual(result.approval_status, 'pending')

        # Aprova a correção formalmente
        approval_res = self.fidelity.approve_correction(result.id, approver='Diretor de Arte')
        self.assertEqual(approval_res['status'], 'approved')
        reloaded = self.fidelity.get_check(result.id)
        self.assertEqual(reloaded.approval_status, 'approved')

        # Testa auto_regenerate sujeito a orçamento
        result_auto = self.fidelity.check_fidelity(
            campaign_id=self.cid,
            product_id=self.prod_id,
            asset_id='asset-auto.png',
            slide_id=self.s1,
            fixture_override=FIXTURE_ALTERED_PRODUCT,
            mode_override='auto_regenerate',
        )
        self.assertEqual(result_auto.approval_status, 'auto_applied')

        # Se orçamento estiver esgotado, auto_regenerate reverte para aprovação manual
        self.cost.set_campaign_budget(self.cid, limit=1.0)
        self.cost.record_direct_spend(
            campaign_id=self.cid,
            asset_id='asset-previous.png',
            stage='generation',
            provider='gemini',
            model='imagen-3.0-generate-002',
            estimated_cost=1.0,
            actual_cost=1.50,
        )
        result_blocked = self.fidelity.check_fidelity(
            campaign_id=self.cid,
            product_id=self.prod_id,
            asset_id='asset-blocked.png',
            slide_id=self.s1,
            fixture_override=FIXTURE_ALTERED_PRODUCT,
            mode_override='auto_regenerate',
        )
        self.assertEqual(result_blocked.approval_status, 'pending')
        self.assertIn('Orçamento limite atingido', result_blocked.suggested_fix)

    def test_version_registration_tracks_all_required_metadata(self):
        # M06-A03: Versões registram motivo, solicitante, engine, prompt deduplicado/referenciado, referências, custo, fidelidade e timestamp
        self.queue.enqueue_campaign_execution(self.cid)
        self.worker.run_all_pending()

        versions = self.queue.list_versions_for_slide(self.s1)
        self.assertEqual(len(versions), 1)
        v = versions[0]

        # Verifica todos os campos obrigatórios da Seção 53 e M06-A03
        self.assertEqual(v.version_number, 1)
        self.assertEqual(v.reason, 'Geração inicial')
        self.assertEqual(v.requester, 'system')
        self.assertEqual(v.provider_id, 'gemini')
        self.assertEqual(v.model_id, 'imagen-3.0-generate-002')
        self.assertIsNotNone(v.prompt_ref)  # Hash deduplicado do prompt
        self.assertIsInstance(v.prompt_ref, str)
        self.assertGreater(len(v.prompt_ref), 0)
        self.assertIsInstance(v.references, list)
        self.assertGreater(v.actual_cost, 0.0)
        self.assertIsNotNone(v.fidelity_score)  # Score de fidelidade calculado
        self.assertGreaterEqual(v.fidelity_score, 0.0)
        self.assertIsNotNone(v.created_at)
        self.assertTrue(v.is_current)

    def test_compare_up_to_three_versions_choose_restore_and_use_as_base(self):
        # M06-A04: Comparar até três versões, escolher, restaurar e usar como base preserva histórico; regeneração afeta apenas asset/slide selecionado
        self.queue.enqueue_campaign_execution(self.cid)
        self.worker.run_all_pending()

        # Cria v2 e v3 via intervenção localizada no mesmo slide
        self.queue.regenerate_slide(self.cid, self.s1, new_prompt='Slide 1 v2 com luz dourada suave')
        self.worker.run_all_pending()

        self.queue.regenerate_slide(self.cid, self.s1, new_prompt='Slide 1 v3 com reflexo em madeira', engine_override='openai:dall-e-3')
        self.worker.run_all_pending()

        versions = self.queue.list_versions_for_slide(self.s1)
        self.assertEqual(len(versions), 3)
        v1, v2, v3 = versions[0], versions[1], versions[2]

        # 1. Comparação lado a lado de até 3 versões (Seção 54)
        comp = self.queue.compare_versions([v1.id, v2.id, v3.id])
        self.assertEqual(len(comp['versions']), 3)
        self.assertTrue(comp['differences']['engines_differ'])  # Gemini vs OpenAI
        self.assertTrue(comp['differences']['prompts_differ'])

        # Tentativa de comparar mais de 3 versões é recusada conforme Seção 54
        with self.assertRaises(ValueError):
            self.queue.compare_versions([v1.id, v2.id, v3.id, 'fake-id-4'])

        # 2. Escolher versão como ativa (choose)
        self.queue.choose_version(v2.id, chooser='Diretoria')
        reloaded_v2 = self.queue.get_version(v2.id)
        reloaded_v3 = self.queue.get_version(v3.id)
        self.assertTrue(reloaded_v2.is_current)
        self.assertFalse(reloaded_v3.is_current)

        # 3. Restaurar versão anterior (restore) sem apagar histórico (Seção 53, 80)
        self.queue.restore_version(v1.id, restorer='Diretoria')
        all_vers = self.queue.list_versions_for_slide(self.s1)
        self.assertEqual(len(all_vers), 3)  # Nenhuma versão foi deletada!
        self.assertTrue(self.queue.get_version(v1.id).is_current)

        # 4. Usar versão como base (use_as_base) para intervenção localizada
        job = self.queue.use_version_as_base(v2.id, new_prompt='Slide 1 v4 baseado na v2 com mais nitidez', requester='Fotógrafo')
        self.assertEqual(job.slide_id, self.s1)
        self.assertEqual(job.priority, 5)  # Prioridade de intervenção
        self.worker.run_all_pending()

        all_vers_after = self.queue.list_versions_for_slide(self.s1)
        self.assertEqual(len(all_vers_after), 4)
        v4 = all_vers_after[-1]
        self.assertEqual(v4.version_number, 4)
        self.assertEqual(v4.parent_version_id, v2.id)
        self.assertIn('v2', v4.reason)

        # 5. Registrar aprendizado (record_learning)
        lid = self.queue.record_version_learning(v2.id, 'A luz dourada valorizou os reflexos do vidro âmbar')
        self.assertIsNotNone(lid)
        learnings = self.queue.list_learnings_for_slide(self.s1)
        self.assertEqual(len(learnings), 1)
        self.assertEqual(learnings[0]['learning_note'], 'A luz dourada valorizou os reflexos do vidro âmbar')

    def test_fixtures_correct_altered_and_threshold_boundaries_contract(self):
        # M06-A05: Fixtures de produto correto, produto/etiqueta/logo alterados e limites de threshold validam o contrato; não apresentar como acurácia real
        # 1. Produto correto
        res_ok = self.fidelity.check_fidelity(
            self.cid, self.prod_id, 'asset.png', fixture_override=FIXTURE_CORRECT_PRODUCT, threshold_override=85.0
        )
        self.assertTrue(res_ok.passed)
        self.assertEqual(res_ok.formatted_score, 'Fidelidade: 94/100')
        self.assertIn('estimativa de visão computacional', res_ok.to_dict()['disclaimer'])

        # 2. Produto alterado (forma, proporção, materiais)
        res_alt_prod = self.fidelity.check_fidelity(
            self.cid, self.prod_id, 'asset.png', fixture_override=FIXTURE_ALTERED_PRODUCT, threshold_override=85.0
        )
        self.assertFalse(res_alt_prod.passed)
        self.assertLess(res_alt_prod.score, 85.0)
        self.assertTrue(any(d.attribute == 'shape' for d in res_alt_prod.discrepancies))

        # 3. Etiqueta alterada
        res_alt_lbl = self.fidelity.check_fidelity(
            self.cid, self.prod_id, 'asset.png', fixture_override=FIXTURE_ALTERED_LABEL, threshold_override=85.0
        )
        self.assertFalse(res_alt_lbl.passed)
        self.assertTrue(any(d.attribute == 'label' for d in res_alt_lbl.discrepancies))

        # 4. Logo alterado
        res_alt_logo = self.fidelity.check_fidelity(
            self.cid, self.prod_id, 'asset.png', fixture_override=FIXTURE_ALTERED_LOGO, threshold_override=85.0
        )
        self.assertFalse(res_alt_logo.passed)
        self.assertTrue(any(d.attribute == 'logo' for d in res_alt_logo.discrepancies))

        # 5. Limites de threshold (boundaries)
        # Threshold de 95: score 94 falha
        res_thresh_high = self.fidelity.check_fidelity(
            self.cid, self.prod_id, 'asset.png', fixture_override=FIXTURE_CORRECT_PRODUCT, threshold_override=95.0
        )
        self.assertFalse(res_thresh_high.passed)

        # Threshold de 90: score 94 passa
        res_thresh_low = self.fidelity.check_fidelity(
            self.cid, self.prod_id, 'asset.png', fixture_override=FIXTURE_CORRECT_PRODUCT, threshold_override=90.0
        )
        self.assertTrue(res_thresh_low.passed)


if __name__ == '__main__':
    unittest.main()
