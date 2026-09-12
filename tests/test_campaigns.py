"""Testes unitários de Campanhas, Storyboard, Pipeline e Sistema de Aprovação (M04-A01 a M04-A05)."""
from pathlib import Path
import tempfile
import unittest

from kiros.application import Application
from kiros.campaigns.models import (
    UnapprovedExecutionError,
    InvalidStateTransitionError,
    VALID_CAMPAIGN_STATES,
    VALID_APPROVAL_MODES,
)
from kiros.core.contracts import Provenance


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = Application(Path(self.tmp.name))
        self.mgr = self.app.campaigns
        self.director = self.app.director
        self.library = self.app.library

        # Cadastra produtos de referência na biblioteca
        self.library.create_product('vela-alecrim', 'Vela Aromática Alecrim & Algodão')

    def provenance(self, ref='teste-campanhas'):
        return Provenance('user', ref, '2026-09-12T12:00:00+00:00')

    def test_campaign_persistence_and_explicit_states(self):
        # M04-A01: Campanha persiste briefing, estratégia, produtos, storyboard e pipeline com estados explícitos
        briefing = {
            'primary_objective': 'lançamento',
            'secondary_objective': 'awareness',
            'visual_tone': 'Minimalista nórdico',
            'summary': 'Lançamento de nova vela em vidro âmbar',
        }
        strategy = {'funnel_stage': 'Descoberta', 'pillar': 'produtos'}
        products = [{'product_id': 'vela-alecrim', 'name': 'Vela Aromática Alecrim & Algodão'}]

        cid = self.mgr.create_campaign(
            title='Velas de Outono 2026',
            briefing=briefing,
            strategy=strategy,
            products=products,
            approval_mode='minimal',
            provenance=self.provenance(),
        )

        camp = self.mgr.get_campaign(cid)
        self.assertIsNotNone(camp)
        self.assertEqual(camp.title, 'Velas de Outono 2026')
        self.assertEqual(camp.status, 'draft')
        self.assertEqual(camp.plan_version, 1)
        self.assertIn(camp.status, VALID_CAMPAIGN_STATES)
        self.assertIn(camp.approval_mode, VALID_APPROVAL_MODES)
        self.assertEqual(len(camp.products), 1)
        self.assertEqual(camp.products[0]['product_id'], 'vela-alecrim')

    def test_pipeline_minimum_steps_and_localized_editing(self):
        # M04-A02: Pipeline usa mínimo de etapas necessário; engine por slide e edição localizada preservam etapas não afetadas
        briefing = {'primary_objective': 'awareness', 'summary': 'Cenário acolhedor'}
        cid = self.mgr.create_campaign('Campanha Minimal', briefing, {}, [])

        # Adiciona 2 slides
        s1 = self.mgr.add_storyboard_slide(
            cid,
            title='Slide 1: Ambiente Acolhedor',
            visual_prompt='Vela sobre aparador de madeira em sala iluminada',
            framing='wide',
            engine_override='gemini:imagen-3.0-generate-002',
        )
        s2 = self.mgr.add_storyboard_slide(
            cid,
            title='Slide 2: Detalhe do Vidro Âmbar',
            visual_prompt='Close-up do frasco com reflexos quentes',
            framing='detail',
            engine_override='openai:dall-e-3',
        )

        camp = self.mgr.get_campaign(cid)
        # Exatamente 2 etapas no pipeline (1 etapa enxuta por slide, menor número necessário)
        self.assertEqual(len(camp.pipeline_steps), 2)
        step1 = next(p for p in camp.pipeline_steps if p.slide_id == s1)
        step2 = next(p for p in camp.pipeline_steps if p.slide_id == s2)

        self.assertEqual(step1.provider_id, 'gemini')
        self.assertEqual(step1.model_id, 'imagen-3.0-generate-002')
        self.assertEqual(step2.provider_id, 'openai')
        self.assertEqual(step2.model_id, 'dall-e-3')

        # Edição localizada: altera apenas a etapa do slide 1
        initial_version = camp.plan_version
        self.mgr.update_pipeline_step(
            step_id=step1.id,
            name='Etapa 1 Customizada com Fast',
            provider_id='gemini',
            model_id='imagen-3.0-fast-generate-001',
        )

        updated_camp = self.mgr.get_campaign(cid)
        updated_step1 = next(p for p in updated_camp.pipeline_steps if p.slide_id == s1)
        updated_step2 = next(p for p in updated_camp.pipeline_steps if p.slide_id == s2)

        # Etapa 1 foi atualizada
        self.assertEqual(updated_step1.name, 'Etapa 1 Customizada com Fast')
        self.assertEqual(updated_step1.model_id, 'imagen-3.0-fast-generate-001')

        # Etapa 2 PRESERVADA intocada (M04-A02)
        self.assertEqual(updated_step2.provider_id, 'openai')
        self.assertEqual(updated_step2.model_id, 'dall-e-3')
        self.assertEqual(updated_step2.name, 'Geração de Imagem com dall-e-3')

        # Edição material incrementou a versão do plano
        self.assertGreater(updated_camp.plan_version, initial_version)

    def test_slide_engine_override_preserves_other_slides(self):
        # M04-A02: Engine por slide preserva os outros slides
        cid = self.mgr.create_campaign('Multi-Engine Test', {}, {}, [])
        s1 = self.mgr.add_storyboard_slide(cid, 'Slide A', 'Prompt A')
        s2 = self.mgr.add_storyboard_slide(cid, 'Slide B', 'Prompt B')

        # Altera engine apenas do slide 2
        self.mgr.update_slide_engine(s2, 'openai:dall-e-3')

        camp = self.mgr.get_campaign(cid)
        step_a = next(p for p in camp.pipeline_steps if p.slide_id == s1)
        step_b = next(p for p in camp.pipeline_steps if p.slide_id == s2)

        self.assertEqual(step_b.provider_id, 'openai')
        self.assertEqual(step_b.model_id, 'dall-e-3')
        # Slide A permaneceu inalterado
        self.assertEqual(step_a.provider_id, 'gemini')

    def test_approval_screen_data_contains_required_fields(self):
        # M04-A03: Tela de aprovação mostra objetivo, conceito, produtos, storyboard, engine, pipeline, gerações, custo e confiança
        briefing = {
            'primary_objective': 'educação',
            'secondary_objective': 'relacionamento',
            'summary': 'Guia aromacológico de cuidados com a vela',
            'visual_tone': 'Calmo e sereno',
            'confidence': 0.92,
        }
        products = [{'product_id': 'vela-alecrim', 'name': 'Vela Alecrim'}]
        cid = self.mgr.create_campaign('Educativo Velas', briefing, {}, products)
        self.mgr.add_storyboard_slide(cid, 'Passo 1', 'Aparando o pavio de algodão', framing='close-up')
        self.mgr.add_storyboard_slide(cid, 'Passo 2', 'Primeira queima de 2 horas', framing='medium')

        data = self.mgr.get_approval_screen_data(cid)

        # Seção 75 campos obrigatórios
        self.assertEqual(data['objective'], 'EDUCAÇÃO')
        self.assertEqual(data['secondary_objective'], 'relacionamento')
        self.assertIn('Guia aromacológico', data['concept'])
        self.assertEqual(len(data['products']), 1)
        self.assertEqual(data['estimated_generations'], 2)
        self.assertGreater(data['estimated_cost'], 0.0)
        self.assertEqual(data['confidence'], 0.92)
        self.assertEqual(len(data['storyboard']), 2)
        self.assertEqual(len(data['pipeline']), 2)
        self.assertEqual(len(data['engine_summary']), 2)
        self.assertFalse(data['is_approved'])

    def test_approval_modes_and_plan_version_binding(self):
        # M04-A04: Modos minimal/step_by_step/full_control e aprovação vinculada à versão do plano e orçamento
        cid_min = self.mgr.create_campaign('Modo Minimal', {}, {}, [], approval_mode='minimal')
        s1 = self.mgr.add_storyboard_slide(cid_min, 'Slide 1', 'Prompt 1')
        s2 = self.mgr.add_storyboard_slide(cid_min, 'Slide 2', 'Prompt 2')

        # Submete e aprova no modo minimal (aprova tudo)
        self.mgr.submit_for_approval(cid_min)
        camp = self.mgr.get_campaign(cid_min)
        self.assertEqual(camp.status, 'awaiting_approval')

        approval = self.mgr.approve_campaign(cid_min, approver='Diretoria de Arte')
        self.assertTrue(approval.is_valid)
        self.assertEqual(approval.plan_version, camp.plan_version)
        self.assertGreater(approval.estimated_cost, 0.0)

        camp_after = self.mgr.get_campaign(cid_min)
        self.assertEqual(camp_after.status, 'approved')
        self.assertEqual(camp_after.approved_version, camp.plan_version)
        self.assertEqual(camp_after.approved_by, 'Diretoria de Arte')

        # Modo step_by_step: aprovação etapa por etapa
        cid_step = self.mgr.create_campaign('Modo Step by Step', {}, {}, [], approval_mode='step_by_step')
        st1 = self.mgr.add_storyboard_slide(cid_step, 'Slide A', 'Prompt A')
        st2 = self.mgr.add_storyboard_slide(cid_step, 'Slide B', 'Prompt B')

        camp_s = self.mgr.get_campaign(cid_step)
        step_a = camp_s.pipeline_steps[0]
        step_b = camp_s.pipeline_steps[1]

        # Aprova apenas a primeira etapa
        appr_a = self.mgr.approve_step(step_a.id, approver='Revisor Técnico')
        self.assertTrue(appr_a.is_valid)
        self.assertEqual(appr_a.step_id, step_a.id)

        # Campanha ainda não está completamente aprovada
        self.assertNotEqual(self.mgr.get_campaign(cid_step).status, 'approved')

        # Aprova a segunda etapa: agora todas estão aprovadas
        self.mgr.approve_step(step_b.id, approver='Revisor Técnico')
        self.assertEqual(self.mgr.get_campaign(cid_step).status, 'approved')

    def test_material_change_invalidates_approval_and_refuses_unapproved_execution(self):
        # M04-A05: Mudança material invalida aprovação anterior; execução sem aprovação válida é recusada no servidor
        cid = self.mgr.create_campaign('Campanha Segura', {}, {}, [])
        self.mgr.add_storyboard_slide(cid, 'Slide Único', 'Prompt Original', framing='wide')

        # 1. Tentar enfileirar em estado 'draft' ou sem aprovação deve ser RECUSADO
        with self.assertRaises(UnapprovedExecutionError) as ctx:
            self.mgr.queue_execution(cid)
        self.assertIn('Execução recusada', str(ctx.exception))

        # 2. Aprova a versão 2 (v2 após add slide)
        self.mgr.submit_for_approval(cid)
        self.mgr.approve_campaign(cid, approver='Head de Criação')

        camp = self.mgr.get_campaign(cid)
        self.assertEqual(camp.status, 'approved')
        v_approved = camp.plan_version

        # Agora execução é permitida
        self.mgr.queue_execution(cid)
        self.assertEqual(self.mgr.get_campaign(cid).status, 'queued')

        # 3. Simula uma campanha aprovada que sofre alteração material (ex: adição de slide ou edição de etapa)
        cid2 = self.mgr.create_campaign('Campanha Editada Pós-Aprovação', {}, {}, [])
        slide_id = self.mgr.add_storyboard_slide(cid2, 'Slide 1', 'Prompt 1')
        self.mgr.submit_for_approval(cid2)
        self.mgr.approve_campaign(cid2, approver='Head de Criação')

        camp2 = self.mgr.get_campaign(cid2)
        self.assertEqual(camp2.status, 'approved')
        initial_version = camp2.plan_version

        # Edição localizada no pipeline: alteração material!
        step_id = camp2.pipeline_steps[0].id
        self.mgr.update_pipeline_step(step_id, name='Nome Alterado Pós-Aprovação')

        camp2_updated = self.mgr.get_campaign(cid2)
        # A aprovação anterior foi INVALIDADA!
        self.assertNotEqual(camp2_updated.status, 'approved')
        self.assertGreater(camp2_updated.plan_version, initial_version)
        self.assertIsNone(camp2_updated.approved_version)

        # Histórico registra aprovação anterior como is_valid = 0
        self.assertEqual(len(camp2_updated.approvals), 1)
        self.assertFalse(camp2_updated.approvals[0].is_valid)
        self.assertIn('Edição localizada', camp2_updated.approvals[0].invalidation_reason)

        # Tentar enfileirar sem re-aprovar é estritamente RECUSADO no servidor (M04-A05)
        with self.assertRaises(UnapprovedExecutionError) as ctx:
            self.mgr.queue_execution(cid2)
        self.assertIn('Execução recusada', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()

