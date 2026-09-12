"""Testes de Copy, Voz da Marca, Legendas e Governança de Preço (Seções 34-37 e M08-A01, M08-A02, M08-A03)."""
import unittest

from kiros.content.copy_engine import CopyEngine
from kiros.content.models import (
    PROHIBITED_AI_CLICHES,
    PROHIBITED_CTA_FORMULAS,
    PriceApprovalRequiredError,
    MissingProductPriceError,
    ProhibitedContentError,
    CommercialDataFabricationError,
)


class CopyAndVoiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = CopyEngine()

    def test_caption_modes_and_preserves_user_contribution(self):
        """M08-A01: Modos automatic/suggestions/user_provided/ai_plus_user respeitam voz brasileira e preservam contribuição do usuário."""
        ctx = {
            'product_name': 'Vela Alecrim & Flor de Laranjeira',
            'fragrance': 'Alecrim & Flor de Laranjeira',
            'visual_tone': 'Luz natural suave e nórdica',
        }

        # 1. Modo automatic: gera texto na voz da marca
        auto_text = self.engine.generate_automatic_caption(ctx)
        self.assertIn('alecrim & flor de laranjeira', auto_text.lower())
        self.assertNotIn('#', auto_text)
        for cliche in PROHIBITED_AI_CLICHES:
            self.assertNotIn(cliche, auto_text.lower())

        # 2. Modo suggestions: gera 3 opções distintas (Sensorial, Rotina, Minimalista)
        suggestions = self.engine.generate_caption_suggestions(ctx)
        self.assertEqual(len(suggestions), 3)
        styles = {s['style'] for s in suggestions}
        self.assertEqual(styles, {'sensorial', 'rotina', 'minimalista'})
        for s in suggestions:
            self.assertTrue(len(s['text']) > 20)
            self.assertNotIn('#', s['text'])

        # 3. Modo user_provided: preserva contribuição integralmente
        user_input = "Acender uma vela e esquecer do relógio por meia hora."
        full_user = self.engine.build_full_caption(
            mode='user_provided',
            text=user_input,
        )
        self.assertIn(user_input, full_user)

        # 4. Modo ai_plus_user: refina mantendo os termos e intenções do usuário
        raw_draft = "minha ideia é falar sobre o cheiro de alecrim que me lembra a casa da minha avó em minas"
        refined = self.engine.refine_user_copy(raw_draft, ctx)
        self.assertIn("cheiro de alecrim", refined)
        self.assertIn("casa da minha avó em minas", refined)

    def test_no_automatic_hashtags_and_no_editorial_emojis(self):
        """M08-A02: Sem hashtags automáticas ou emojis editoriais; CTA contextual é opcional."""
        ctx = {'fragrance': 'Lavanda & Baunilha'}
        auto_caption = self.engine.generate_automatic_caption(ctx)

        # Sem hashtags
        self.assertNotIn('#', auto_caption)

        # Sem emojis
        violations = self.engine.check_prohibited_elements(auto_caption)
        self.assertEqual(violations, [])

        # Detecção caso usuário ou texto contenha emojis ou hashtags
        text_with_emoji = "Vela relaxante para sua noite 🕯️✨"
        detected = self.engine.check_prohibited_elements(text_with_emoji)
        self.assertTrue(any('emojis' in d.lower() for d in detected))

        text_with_hashtag = "Aroma suave de lavanda #velaaromatica #decor"
        detected_ht = self.engine.check_prohibited_elements(text_with_hashtag)
        self.assertTrue(any('hashtags' in d.lower() for d in detected_ht))

        # Limpeza determinística de emojis e hashtags acidentais
        cleaned = self.engine.clean_emojis_and_hashtags(text_with_emoji)
        self.assertNotIn('🕯️', cleaned)
        self.assertNotIn('✨', cleaned)
        self.assertEqual(cleaned, "Vela relaxante para sua noite")

    def test_cta_optional_contextual_and_bans_artificial_formulas(self):
        """M08-A02: CTA contextual é opcional; proibição de fórmulas artificiais ('comente EU QUERO')."""
        # CTA None / Ausente por padrão (CTA não é obrigatório - Seção 36)
        cta_none = self.engine.generate_cta('none')
        self.assertEqual(cta_none, '')

        # CTA intent_based
        cta_desc = self.engine.generate_cta('intent_based', intent='descoberta')
        self.assertIn('link da bio', cta_desc.lower())

        # Banimento de fórmulas artificiais de CTA
        for formula in PROHIBITED_CTA_FORMULAS:
            violations = self.engine.check_prohibited_elements(formula)
            self.assertTrue(len(violations) > 0, f"Deveria detectar violação em: {formula}")
            with self.assertRaises(ProhibitedContentError):
                self.engine.generate_cta('manual', manual_text=formula)

    def test_price_hidden_by_default_and_requires_justification_and_approval(self):
        """M08-A02 e M08-A03: Preço oculto por padrão; preço só com justificativa, dado real e aprovação."""
        product_with_price = {'name': 'Vela Alecrim', 'price': '118,00'}
        product_without_price = {'name': 'Vela Alecrim'}

        # 1. Oculto por padrão
        show, price = self.engine.validate_and_format_price(show_price=False, product_data=product_with_price)
        self.assertFalse(show)
        self.assertIsNone(price)

        # 2. Tentativa de exibir preço sem dado real no produto -> Erro estrito
        with self.assertRaises(MissingProductPriceError):
            self.engine.validate_and_format_price(
                show_price=True,
                product_data=product_without_price,
                justification="Lançamento de produto",
                approved_by="Diretoria Comercial",
            )

        # 3. Exibição de preço com dado real mas SEM justificativa -> Bloqueio
        with self.assertRaises(PriceApprovalRequiredError):
            self.engine.validate_and_format_price(
                show_price=True,
                product_data=product_with_price,
                justification="",
                approved_by="Diretoria Comercial",
            )

        # 4. Exibição de preço com dado real e justificativa mas SEM aprovador -> Bloqueio
        with self.assertRaises(PriceApprovalRequiredError):
            self.engine.validate_and_format_price(
                show_price=True,
                product_data=product_with_price,
                justification="Transparência em campanha de lançamento",
                approved_by="",
            )

        # 5. Exibição aprovada com todos os requisitos atendidos
        show, price = self.engine.validate_and_format_price(
            show_price=True,
            product_data=product_with_price,
            justification="Transparência em campanha de lançamento",
            approved_by="Diretoria Comercial",
        )
        self.assertTrue(show)
        self.assertEqual(price, "R$ 118,00")

    def test_never_invent_price_stock_promotion_or_availability(self):
        """M08-A03: Nunca inventar preço, estoque, promoção ou disponibilidade (Seção 35)."""
        # Invenção de escassez comercial
        fake_stock = "Corra! Restam apenas 2 unidades no estoque limitado!"
        violations = self.engine.detect_commercial_fabrication(fake_stock)
        self.assertTrue(any('escassez' in v.lower() or 'estoque' in v.lower() for v in violations))

        # Invenção de promoção
        fake_promo = "Aproveite 50% off somente hoje na queima de estoque!"
        violations_promo = self.engine.detect_commercial_fabrication(fake_promo)
        self.assertTrue(any('promoção' in v.lower() for v in violations_promo))

        # Invenção de preço não autorizado
        fake_price = "Por apenas R$ 49,90 você leva o kit completo."
        violations_price = self.engine.detect_commercial_fabrication(fake_price, allowed_price=None)
        self.assertTrue(any('preço não autorizado' in v.lower() for v in violations_price))

        # Preço autorizado não gera violação
        legit_text = "Valor oficial: R$ 118,00 no catálogo."
        no_violations = self.engine.detect_commercial_fabrication(legit_text, allowed_price="R$ 118,00")
        self.assertEqual(no_violations, [])


if __name__ == '__main__':
    unittest.main()

