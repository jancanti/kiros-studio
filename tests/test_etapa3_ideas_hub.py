"""Testes otimizados para a Etapa 3: Hub de Ideias e Recomendações de IA."""
import unittest
import tempfile
from pathlib import Path
from kiros.application import Application
from kiros.ui.creator import dispatch_creator_action, render_creator


class TestEtapa3IdeasHub(unittest.TestCase):
    def test_etapa3_generate_ai_recommendations(self):
        """Garante a geração adaptativa de ideias sem consumo em segundo plano."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            app = Application(Path(tmp_dir))

            # Cadastra um produto rico para testar o dinamismo das sugestões
            app.library.create_product('vela-alecrim', 'Vela Alecrim & Algodão', None, 'Test')

            recs = app.director.generate_ai_recommendations(limit=3)

            # Deve retornar exatamente 3 ideias adaptativas
            self.assertEqual(len(recs), 3)
            themes = [r['theme'] for r in recs]
            self.assertIn('Estética & Luxo', themes)
            self.assertIn('Ingredientes & Qualidade', themes)
            self.assertIn('Ritual & Ocasião', themes)

            # As ideias devem ter sido salvas no banco de dados local (SQLite) para cache permanente
            active_count = app.idea_bank.count_active_ideas('lifestyle') + app.idea_bank.count_active_ideas('produtos') + app.idea_bank.count_active_ideas('relacionamento')
            self.assertGreaterEqual(active_count, 1)

    def test_etapa3_use_idea_action(self):
        """Garante que o clique em 'Criar esta Campanha em 1-Clique' estrutura o briefing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            app = Application(Path(tmp_dir))

            # Simula a submissão do formulário de 1-Clique
            res_query = dispatch_creator_action(
                app,
                'use_idea',
                {
                    'title': 'Carrossel: O Ritual de Acender a Vela',
                    'concept': 'Iluminação oblíqua natural e momento de leitura à noite.',
                    'objective': 'awareness',
                }
            )

            self.assertIn('briefing_done=1', res_query)
            self.assertIn('raw_briefing', res_query)
            self.assertIn('Ritual+de+Acender', res_query)

    def test_etapa3_render_creator_hub_ui(self):
        """Garante que a tela /criar renderiza os cards de ideias recomendadas."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            app = Application(Path(tmp_dir))

            html = render_creator(app, {})
            self.assertIn("💡 Ideias Recomendadas para Você", html)
            self.assertIn("✨ Gerar Novas Ideias", html)
            self.assertIn("⚡ Criar esta Campanha em 1-Clique", html)


if __name__ == '__main__':
    unittest.main()
