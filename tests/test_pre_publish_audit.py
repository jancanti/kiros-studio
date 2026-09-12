"""Testes de Auditoria Pré-Publicação e Checklist de Governança Editorial (M08-A05)."""
import unittest

from kiros.content.models import CaptionContent, StorySequence, StoryFrame
from kiros.content.audit import PrePublishAuditor
from kiros.content.copy_engine import CopyEngine
from kiros.content.stories_engine import StoriesEngine


class PrePublishAuditTests(unittest.TestCase):
    def setUp(self):
        self.copy_engine = CopyEngine()
        self.stories_engine = StoriesEngine()
        self.auditor = PrePublishAuditor(self.copy_engine, self.stories_engine)

    def test_audit_detects_prohibited_emojis_and_blocks_publication(self):
        """M08-A05: Auditoria bloqueia publicação se houver emojis em legendas ou CTAs (Seção 34)."""
        caption = CaptionContent(
            id="c1",
            campaign_id="camp-1",
            slide_id="slide-1",
            text="Vela aromática com queima limpa e lenta 🕯️",
            cta_text="Veja na bio ✨",
        )
        res = self.auditor.audit_caption(caption)
        self.assertFalse(res.is_ready)
        self.assertTrue(any('emojis' in r.lower() for r in res.blocked_reasons))

        check_emoji = next(c for c in res.checks if c.check_id == 'no_emojis')
        self.assertEqual(check_emoji.status, 'blocked')

    def test_audit_detects_automatic_hashtags_and_blocks_publication(self):
        """M08-A05: Auditoria bloqueia publicação se houver hashtags automáticas (Seção 34)."""
        caption = CaptionContent(
            id="c2",
            campaign_id="camp-1",
            slide_id="slide-1",
            text="Aroma suave para começar o dia bem. #velaaromatica #kirossp",
        )
        res = self.auditor.audit_caption(caption)
        self.assertFalse(res.is_ready)
        self.assertTrue(any('hashtags' in r.lower() for r in res.blocked_reasons))

        check_ht = next(c for c in res.checks if c.check_id == 'no_auto_hashtags')
        self.assertEqual(check_ht.status, 'blocked')

    def test_audit_detects_ai_cliches_and_blocks_publication(self):
        """M08-A05: Auditoria detecta clichês de IA e exige voz natural brasileira (Seção 34)."""
        caption = CaptionContent(
            id="c3",
            campaign_id="camp-1",
            slide_id="slide-1",
            text="No mundo agitado de hoje, descubra a magia de transformar seu ambiente.",
        )
        res = self.auditor.audit_caption(caption)
        self.assertFalse(res.is_ready)
        self.assertTrue(any('clichês' in r.lower() for r in res.blocked_reasons))

    def test_audit_detects_commercial_fabrication_and_missing_price_approval(self):
        """M08-A05: Auditoria bloqueia invenção comercial e preço sem justificativa/aprovação (Seções 35 e 37)."""
        # 1. Invenção de escassez e desconto
        caption_fake = CaptionContent(
            id="c4",
            campaign_id="camp-1",
            slide_id="slide-1",
            text="Últimas unidades com 50% off somente hoje!",
        )
        res_fake = self.auditor.audit_caption(caption_fake)
        self.assertFalse(res_fake.is_ready)
        self.assertTrue(any('invenção' in r.lower() or 'escassez' in r.lower() for r in res_fake.blocked_reasons))

        # 2. Exibição de preço sem justificativa e sem aprovação
        caption_unapproved_price = CaptionContent(
            id="c5",
            campaign_id="camp-1",
            slide_id="slide-1",
            text="Vela aromática em vidro âmbar.",
            show_price=True,
            price_value="R$ 118,00",
            price_justification="",  # ausente
            price_approved_by="",    # ausente
        )
        res_price = self.auditor.audit_caption(caption_unapproved_price)
        self.assertFalse(res_price.is_ready)
        self.assertTrue(any('justificativa' in r.lower() or 'aprovação' in r.lower() for r in res_price.blocked_reasons))

    def test_audit_approves_clean_and_compliant_caption(self):
        """M08-A05: Auditoria aprova legenda limpa, na voz brasileira e com governança atendida."""
        caption_ok = CaptionContent(
            id="c6",
            campaign_id="camp-1",
            slide_id="slide-1",
            text="O aroma de alecrim preenche a sala aos poucos. Um detalhe simples que muda o ritmo da manhã.",
            cta_text="Disponível no link da bio.",
            destination_url="https://instagram.com/kiros.sp",
            show_price=False,
        )
        res = self.auditor.audit_caption(caption_ok)
        self.assertTrue(res.is_ready)
        self.assertEqual(res.blocked_reasons, [])
        for c in res.checks:
            self.assertIn(c.status, ('passed', 'warning'))

    def test_audit_story_sequence_compliance_and_rejections(self):
        """M08-A05: Auditoria de Stories valida planejamento sequencial próprio e justificativa de interações."""
        # 1. Sequência com apenas 1 frame (redimensionamento de feed) -> Bloqueada
        single_frame_seq = StorySequence(
            id="s-bad",
            campaign_id="c-1",
            title="Story feed esticado",
            frames=[
                StoryFrame(id="f1", sequence_id="s-bad", frame_order=1, narrative_role="hook", title="F1", overlay_text="Vela", visual_prompt="9:16")
            ],
        )
        res_bad = self.auditor.audit_story_sequence(single_frame_seq)
        self.assertFalse(res_bad.is_ready)
        self.assertTrue(any('planejamento de sequência' in r.lower() for r in res_bad.blocked_reasons))

        # 2. Sequência planejada e justificada -> Aprovada
        seq_ok = self.stories_engine.plan_sequence(
            title="Sequência de Sucesso",
            story_type="derived_from_campaign",
        )
        res_ok = self.auditor.audit_story_sequence(seq_ok)
        self.assertTrue(res_ok.is_ready)
        self.assertEqual(res_ok.blocked_reasons, [])


if __name__ == '__main__':
    unittest.main()

