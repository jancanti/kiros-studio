"""Testes do Motor de Layout Determinístico (Seção 28 e Critérios M07-A01, M07-A05)."""
import unittest

from kiros.layout.engine import LayoutEngine
from kiros.layout.models import (
    FORMAT_4_5,
    FORMAT_9_16,
    FORMAT_DIMENSIONS,
    SAFE_AREAS,
    HeadlineElement,
    ImageElement,
    LogoElement,
    CTAElement,
    DecorativeElement,
    SlideLayout,
    LayoutValidationError,
)


class LayoutEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = LayoutEngine()
        self.sample_layout_4_5 = SlideLayout(
            id='lay-test-4-5',
            campaign_id='camp-1',
            slide_id='slide-1',
            format=FORMAT_4_5,
            headline=HeadlineElement(
                text='Velas de Outono: Conforto em Vidro Âmbar',
                font_family='Rubik',
                font_size=52,
                font_weight=600,
                color='#1f2421',
                position_x=80,
                position_y=140,
                max_width=920,
            ),
            image=ImageElement(
                framing='medium',
                scale=1.0,
                lighting='natural_lateral',
                position_x=0,
                position_y=0,
            ),
            logo=LogoElement(
                brand_name='KIROS',
                aspect_ratio_locked=True,
                position_x=80,
                position_y=70,
                scale=1.0,
                color='#273b32',
            ),
            cta=CTAElement(
                text='Descubra a Nova Coleção',
                style='pill',
                position_x=80,
                position_y=1220,
                font_size=24,
                bg_color='#273b32',
                text_color='#ffffff',
            ),
            decorative=DecorativeElement(
                kind='badge',
                label='AROMAS BOTÂNICOS',
                position_x=80,
                position_y=1140,
            ),
        )

    def test_mathematical_proportions_4_5_and_9_16(self):
        """M07-A01 e M07-A05: Comprova proporções matemáticas exatas 0.8 (4:5) e 0.5625 (9:16)."""
        w45, h45 = self.engine.get_dimensions(FORMAT_4_5)
        self.assertEqual((w45, h45), (1080, 1350))
        self.assertAlmostEqual(w45 / h45, 0.80, places=4)
        self.assertTrue(self.engine.validate_proportions(FORMAT_4_5))

        w916, h916 = self.engine.get_dimensions(FORMAT_9_16)
        self.assertEqual((w916, h916), (1080, 1920))
        self.assertAlmostEqual(w916 / h916, 0.5625, places=4)
        self.assertTrue(self.engine.validate_proportions(FORMAT_9_16))

        with self.assertRaises(LayoutValidationError):
            self.engine.get_dimensions('1:1')

    def test_exact_text_rendering_without_llm(self):
        """M07-A01: Comprova renderização de texto exato, sem caracteres modificados ou alucinação."""
        exact_headline = 'Aromas & Botânica: Edição Limitada Sorocaba / SP 2026!'
        exact_cta = 'Garanta o Seu Frasco Exclusivo'
        exact_dec = 'LINHA ESPECIAL DE OUTONO'

        self.sample_layout_4_5.headline.text = exact_headline
        self.sample_layout_4_5.cta.text = exact_cta
        self.sample_layout_4_5.decorative.label = exact_dec

        svg = self.engine.render_svg(self.sample_layout_4_5)

        # O texto deve estar exatamente presente no SVG gerado
        self.assertIn('Aromas &amp; Botânica:', svg)
        self.assertIn('Garanta o Seu Frasco Exclusivo', svg)
        self.assertIn('LINHA ESPECIAL DE OUTONO', svg)
        self.assertIn('KIROS', svg)

        # Metadados estruturados
        exported = self.engine.export_layout_data(self.sample_layout_4_5)
        self.assertEqual(exported['exact_texts']['headline'], exact_headline)
        self.assertEqual(exported['exact_texts']['cta'], exact_cta)
        self.assertEqual(exported['exact_texts']['decorative_label'], exact_dec)
        self.assertEqual(exported['exact_texts']['brand_name'], 'KIROS')

    def test_logo_aspect_ratio_locked_and_semantic_groups(self):
        """M07-A01 e M07-A05: Comprova preservação das proporções do logo e grupos semânticos obrigatórios."""
        svg = self.engine.render_svg(self.sample_layout_4_5)

        # 5 elementos semânticos obrigatórios da Seção 28
        self.assertIn('id="headline"', svg)
        self.assertIn('id="image"', svg)
        self.assertIn('id="logo"', svg)
        self.assertIn('id="cta"', svg)
        self.assertIn('id="decorative"', svg)

        # Verificação do logotipo oficial com proporção travada
        self.assertTrue(self.sample_layout_4_5.logo.aspect_ratio_locked)
        self.assertIn('transform="translate(80, 70) scale(1.0)"', svg)
        self.assertIn('KIROS', svg)
        self.assertIn('AROMAS · BRASIL', svg)

    def test_safe_areas_prevent_clipping_in_4_5_and_9_16(self):
        """M07-A05: Comprova cálculo de safe areas para Feed (4:5) e Stories (9:16) sem cortes de UI."""
        # Layout dentro das safe areas no 4:5
        warnings = self.engine.validate_safe_zones(self.sample_layout_4_5)
        self.assertEqual(warnings, [])

        # Força elemento fora da safe area no 4:5
        bad_layout = SlideLayout(
            id='bad-lay',
            campaign_id='camp-1',
            slide_id='s-1',
            format=FORMAT_4_5,
            headline=HeadlineElement(text='Título', position_x=20, position_y=30),  # Margem esquerda e topo violadas
            image=ImageElement(),
            logo=LogoElement(position_x=1050, position_y=70),  # Margem direita violada
            cta=CTAElement(position_x=80, position_y=1330),    # Margem inferior violada
        )
        bad_warnings = self.engine.validate_safe_zones(bad_layout)
        self.assertGreaterEqual(len(bad_warnings), 3)

        # Adaptação para 9:16 respeita safe area vertical de Stories (top 250px e bottom 350px)
        adapted_9_16 = self.engine.adapt_format(self.sample_layout_4_5, FORMAT_9_16)
        self.assertEqual(adapted_9_16.format, FORMAT_9_16)

        # Logo e headline devem estar abaixo do topo seguro (250px)
        self.assertGreaterEqual(adapted_9_16.logo.position_y, SAFE_AREAS[FORMAT_9_16]['top'])
        self.assertGreaterEqual(adapted_9_16.headline.position_y, SAFE_AREAS[FORMAT_9_16]['top'])

        # CTA e decorative devem estar acima do rodapé seguro (1920 - 350 = 1570)
        max_safe_y = 1920 - SAFE_AREAS[FORMAT_9_16]['bottom']
        self.assertLessEqual(adapted_9_16.cta.position_y, max_safe_y)
        self.assertLessEqual(adapted_9_16.decorative.position_y, max_safe_y)

        # Sem avisos de safe zone no layout adaptado
        adapted_warnings = self.engine.validate_safe_zones(adapted_9_16)
        self.assertEqual(adapted_warnings, [])

    def test_deterministic_text_wrapping(self):
        """M07-A01: Comprova quebra de linha determinística sem quebras indesejadas de palavras."""
        text = "Vela Aromática Alecrim & Algodão em Vidro Âmbar Feita à Mão"
        lines = self.engine.wrap_text(text, max_chars_per_line=24)
        self.assertIsInstance(lines, list)
        self.assertTrue(len(lines) >= 2)
        # Nenhuma linha excede de forma desmedida
        for l in lines:
            self.assertTrue(len(l) <= 28)
        # Recomposição de todas as palavras é idêntica ao original
        self.assertEqual(' '.join(lines), text)

    def test_export_svg_structure_and_defs(self):
        """M07-A01: Comprova estrutura XML válida de SVG standalone com imports de fontes Rubik e Inter."""
        svg = self.engine.export_svg(self.sample_layout_4_5)
        self.assertTrue(svg.startswith('<svg xmlns="http://www.w3.org/2000/svg"'))
        self.assertTrue(svg.endswith('</svg>'))
        self.assertIn('viewBox="0 0 1080 1350"', svg)
        self.assertIn('fonts.googleapis.com', svg)
        self.assertIn('Rubik', svg)
        self.assertIn('Inter', svg)


if __name__ == '__main__':
    unittest.main()

