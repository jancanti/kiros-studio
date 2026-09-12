"""Teste de integração end-to-end do ciclo completo da V1 (M12-A02 e Seção 86).

Fluxo completo:
1. Ideia (Creative Director & Banco de Ideias)
2. Campanha (Briefing, Estratégia e Storyboard)
3. Aprovação Formal do Plano (Governança e Limite Orçamentário)
4. Geração Mock (Fila de Execução e Worker)
5. Fidelidade (Fidelity Check e Registro de Versões)
6. Layout (Layout Engine, Safe Areas e Composição SVG 4:5)
7. Copy (Copy Engine, Voz e Stories Narrativos)
8. Auditoria Pré-Publicação (7 dimensões com recusa sem confirmação)
9. Publicação Mock (Agendamento no Calendário e Publicador com Confirmação Humana)
10. Medição (Métricas de Desempenho e Saturação)
11. Aprendizado (Correção local, Proposta e Memória Permanente com Aprovador)
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from kiros.application import Application
from kiros.core.contracts import Provenance
from kiros.layout.models import FORMAT_4_5, CTAElement, HeadlineElement


class EndToEndV1PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data_dir = Path(self.tmp.name)
        self.app = Application(self.data_dir)

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def test_complete_v1_lifecycle_flow(self):
        """M12-A02: Executa o ciclo completo da ideia até o aprendizado permanente."""
        # -------------------------------------------------------------
        # 0. Setup da Marca e Produto
        # -------------------------------------------------------------
        self.app.library.propose('brand', 'global', {
            'colors': 'Verde Floresta e Âmbar',
            'fonts': 'Rubik e Inter',
            'photography': 'Luz natural suave e texturas acolhedoras',
        }, 'setup')
        # Aprova versão inicial da marca
        state = self.app.library.snapshot()
        latest_bible = state['bible_versions'][-1]
        self.app.library.approve(latest_bible['id'], 'Diretora Criativa')

        # Cadastra Produto e Referência Visual
        self.app.library.create_product('vela-alecrim', 'Vela Aromática Alecrim Silvestre', 100, 'setup')
        photo_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRfixture'
        ref_id = self.app.library.add_reference(
            photo_bytes,
            product_id='vela-alecrim',
            scope='permanent',
            origin='own',
            source_reference='Estúdio Interno KIROS',
            rights='confirmed',
            angle='front',
            quality=5,
        )
        self.assertTrue(bool(ref_id))

        # -------------------------------------------------------------
        # 1. Ideia (Creative Director & Banco de Ideias)
        # -------------------------------------------------------------
        idea_id = self.app.idea_bank.add_idea(
            title='Manhã Revigorante com Alecrim',
            concept='Fotografia de mesa de café da manhã com vela aromática emanando frescor matinal',
            pillar='lifestyle',
            provenance=Provenance('user', 'ideation', self._now()),
        )
        self.assertTrue(bool(idea_id))
        self.app.idea_bank.pin_idea(idea_id)
        active_ideas = self.app.idea_bank.list_ideas(pillar='lifestyle')
        self.assertTrue(any(i['id'] == idea_id for i in active_ideas))

        # -------------------------------------------------------------
        # 2. Campanha (Briefing, Estratégia e Storyboard)
        # -------------------------------------------------------------
        cid = self.app.campaigns.create_campaign(
            title='Lançamento Alecrim Silvestre',
            briefing={'briefing_text': 'Aroma revigorante para começar o dia', 'custom_objective': 'lançamento'},
            strategy={'pillar': 'lifestyle', 'tone': 'revigorante'},
            products=['vela-alecrim'],
        )
        self.assertTrue(bool(cid))

        slide_id = self.app.campaigns.add_storyboard_slide(
            campaign_id=cid,
            title='Slide Principal: Mesa de Café da Manhã',
            visual_prompt='Vela aromática em copo âmbar com detalhes rústicos ao lado de xícara de café e ramos de alecrim',
        )
        self.assertTrue(bool(slide_id))

        # -------------------------------------------------------------
        # 3. Aprovação Formal do Plano (Governança e Limite Orçamentário)
        # -------------------------------------------------------------
        appr = self.app.campaigns.approve_campaign(
            campaign_id=cid,
            approver='Diretora Criativa',
        )
        self.assertIsNotNone(appr)
        camp = self.app.campaigns.get_campaign(cid)
        self.assertEqual(camp.status, 'approved')

        # -------------------------------------------------------------
        # 4. Geração Mock (Fila de Execução e Worker)
        # -------------------------------------------------------------
        # Fila de execução processa etapa mock com armazenamento em disco
        jobs = self.app.queue.enqueue_campaign_execution(cid)
        self.assertGreaterEqual(len(jobs), 1)

        # Worker executa a etapa da fila
        job_result = self.app.worker.run_once()
        self.assertIsNotNone(job_result)
        self.assertEqual(job_result.status, 'completed')

        # -------------------------------------------------------------
        # 5. Fidelidade (Fidelity Check e Versões)
        # -------------------------------------------------------------
        versions = self.app.queue.list_versions_for_slide(slide_id)
        self.assertGreaterEqual(len(versions), 1)
        v0 = versions[0]
        self.assertIsNotNone(v0.asset_id)

        # Checagem de fidelidade
        f_check = self.app.fidelity_service.check_fidelity(
            campaign_id=cid,
            product_id='vela-alecrim',
            asset_id=v0.asset_id,
            slide_id=slide_id,
            version_id=v0.id,
        )
        self.assertGreaterEqual(f_check.score, 80.0)
        self.assertTrue(f_check.passed)

        # -------------------------------------------------------------
        # 6. Layout (Layout Engine, Safe Areas e Composição SVG)
        # -------------------------------------------------------------
        templates = self.app.template_library.list_templates(family='editorial_minimalist')
        self.assertGreaterEqual(len(templates), 1)

        layout = self.app.layout_editor.get_or_create_layout(
            campaign_id=cid,
            slide_id=slide_id,
            target_format=FORMAT_4_5,
            default_headline='Alecrim Silvestre',
            default_cta='Descubra a fragrância',
        )
        self.assertTrue(bool(layout.id))

        # Renderização do SVG matemático (4:5)
        svg_output = self.app.campaigns.render_slide_svg(layout.id, show_safe_areas=True)
        self.assertIn('viewBox="0 0 1080 1350"', svg_output)
        self.assertIn('KIROS', svg_output)
        self.assertIn('safe-area-overlay', svg_output)

        # -------------------------------------------------------------
        # 7. Copy (Copy Engine, Voz e Stories)
        # -------------------------------------------------------------
        caption_text = self.app.copy_engine.generate_automatic_caption({
            'product_name': 'Vela Alecrim Silvestre',
            'fragrance': 'Alecrim Silvestre',
            'occasion': 'começo de manhã',
        })
        self.assertIn('alecrim silvestre', caption_text.lower())
        violations = self.app.copy_engine.check_prohibited_elements(caption_text)
        self.assertEqual(violations, [])

        # Sequência de Stories
        stories_seq = self.app.stories_engine.plan_sequence(
            title='Manhã Revigorante',
            story_type='independent',
            campaign_context={'product_name': 'Vela Alecrim Silvestre'},
        )
        self.assertGreaterEqual(len(stories_seq.frames), 3)

        # -------------------------------------------------------------
        # 8. Auditoria Pré-Publicação (7 Dimensões)
        # -------------------------------------------------------------
        audit_res = self.app.publication_auditor.audit_for_publication(
            campaign_id=cid,
            asset_id=v0.asset_id,
            caption_text=caption_text,
            slide_id=slide_id,
            explicit_confirmation=False,  # Sem confirmação ainda
        )
        # Deve recusar publicação automática sem operador
        self.assertFalse(audit_res.is_ready)
        self.assertIn('Confirmação explícita de operador humano obrigatória para publicar.', audit_res.blocked_reasons)

        # -------------------------------------------------------------
        # 9. Publicação Mock (Agendamento no Calendário e Publicação com Operador)
        # -------------------------------------------------------------
        scheduled_date = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        cal_entry = self.app.calendar.create_entry(
            campaign_id=cid,
            slide_id=slide_id,
            title='Publicação Manhã Revigorante',
            content_type='feed',
            pillar='lifestyle',
            scheduled_for=scheduled_date,
        )
        self.assertTrue(bool(cal_entry.id))

        # Publicação mock com operador explícito
        pub_id = self.app.publisher.publish(
            calendar_entry_id=cal_entry.id,
            campaign_id=cid,
            slide_id=slide_id,
            asset_id=v0.asset_id,
            caption=caption_text,
            media_type='IMAGE',
            explicit_confirmation=True,
            confirmed_by='Operador Humano Responsável',
        )
        self.assertTrue(pub_id.startswith('ig_post_'))

        # -------------------------------------------------------------
        # 10. Medição (Métricas de Desempenho e Saturação)
        # -------------------------------------------------------------
        self.app.insights.record_diversity(
            title='Vela Alecrim Silvestre Matinal',
            dimensions={'pillar': 'lifestyle', 'fragrance': 'alecrim', 'format': 'feed'},
            occurred_at=datetime.now(timezone.utc).isoformat(),
            source='Feed Orgânico',
            campaign_id=cid,
        )
        sat = self.app.insights.saturation(days=30)
        self.assertGreaterEqual(len(sat['samples']), 1)

        # -------------------------------------------------------------
        # 11. Aprendizado (Correção, Proposta e Memória Permanente)
        # -------------------------------------------------------------
        # Registro de correção de campanha gera aprendizado local
        self.app.learning.record_campaign_correction(
            campaign_id=cid,
            slide_id=slide_id,
            correction_note='Priorizar iluminação difusa da manhã sobre o vidro âmbar',
        )
        learnings = self.app.learning.list_learnings(cid)
        self.assertEqual(len(learnings), 1)

        # Proposta de preferência recorrente que exige aprovação formal
        prop_id = self.app.learning.suggest_recurring_preference(
            key='iluminacao_preferida',
            value='Luz solar matinal suave e difusa',
            reason='Observado excelente resultado visual com vela âmbar',
            evidence_count=2,
        )
        self.assertTrue(bool(prop_id))

        # Aprovação formal da proposta
        approved_prop = self.app.learning.approve_proposal(prop_id, approver='Diretora Criativa')
        self.assertEqual(approved_prop['status'], 'approved')
        self.assertEqual(approved_prop['approved_by'], 'Diretora Criativa')

        # Memória permanente oficial gravada com proveniência
        mems = self.app.memory.query_memories(keys=['iluminacao_preferida'])
        self.assertEqual(len(mems), 1)
        self.assertEqual(mems[0]['value'], 'Luz solar matinal suave e difusa')


if __name__ == '__main__':
    unittest.main()
