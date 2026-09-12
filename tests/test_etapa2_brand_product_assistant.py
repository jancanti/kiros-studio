"""Testes otimizados para a Etapa 2: Assistente de Marca e Cadastro Rico de Produtos."""
import unittest
import tempfile
from pathlib import Path
from kiros.application import Application
from kiros.ui.library import dispatch, render_library


class TestEtapa2BrandProductAssistant(unittest.TestCase):
    def test_etapa2_brand_assistant_questionnaire(self):
        """Garante que o assistente de marca cria e aprova a Brand Bible oficial a partir do questionário."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            app = Application(Path(tmp_dir))

            # Verifica que a marca começa limpa (sem Brand Bible oficial)
            self.assertEqual(app.library.brand_for(), {})

            # Executa a ação do assistente de marca
            res_url = dispatch(
                app,
                'brand_assistant',
                {
                    'essence': 'Aromas artesanais de luxo acessível para bem-estar.',
                    'tone': 'Elegante, acolhedora, humana e sofisticada.',
                    'aesthetic': 'Madeira clara, travertino, linho cru e luz oblíqua.',
                    'values': 'Cera 100% vegetal, pavio de puro algodão.',
                },
                {}
            )

            self.assertEqual(res_url, 'marca?saved=1')

            # Agora a Brand Bible oficial deve estar preenchida e aprovada
            official = app.library.brand_for()
            self.assertIsNotNone(official)
            self.assertEqual(official['information'], 'Aromas artesanais de luxo acessível para bem-estar.')
            self.assertEqual(official['photography'], 'Elegante, acolhedora, humana e sofisticada.')
            self.assertEqual(official['materials'], 'Madeira clara, travertino, linho cru e luz oblíqua.')

    def test_etapa2_product_rich_cadastro(self):
        """Garante o cadastro simplificado de produtos ricos com composição e notas olfativas."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            app = Application(Path(tmp_dir))

            # Cadastra um produto rico via formulário simplificado
            res_url = dispatch(
                app,
                'product_rich',
                {
                    'product_id': 'vela-bambu',
                    'name': 'Vela Aromática de Bambu',
                    'volume': '200g',
                    'composition': 'Cera 100% vegetal de coco, pavio de algodão',
                    'olfactory_notes': 'Topo: Folhas Verdes | Corpo: Bambu | Fundo: Musk',
                    'occasion': 'Banhos relaxantes e momentos de leitura',
                },
                {}
            )

            self.assertEqual(res_url, 'marca?saved=1')

            # Verifica que o produto foi criado e a ficha (Product Bible) está aprovada
            products = app.library.snapshot()['products']
            self.assertEqual(len(products), 1)
            self.assertEqual(products[0]['id'], 'vela-bambu')
            self.assertEqual(products[0]['name'], 'Vela Aromática de Bambu')

            pb = app.library.product_bible_for('vela-bambu')
            self.assertIsNotNone(pb)
            self.assertIn('200g', pb['material']['value'])
            self.assertIn('Folhas Verdes', pb['label']['value'])

    def test_etapa2_render_marca_ui(self):
        """Garante a renderização limpa do questionário e do catálogo na página /marca."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            app = Application(Path(tmp_dir))

            html = render_library(app, 'marca', {})
            self.assertIn("✨ Criar ou Atualizar Brand Bible via Questionário", html)
            self.assertIn("🕯️ Catálogo de Produtos (Product Bible)", html)
            self.assertIn("➕ Cadastrar Novo Produto com Informações Ricas", html)


if __name__ == '__main__':
    unittest.main()
