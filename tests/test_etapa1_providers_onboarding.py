"""Testes otimizados para a Etapa 1: Provider Manager, Fallback e Onboarding UI."""
import unittest
import tempfile
from pathlib import Path
from kiros.application import Application


class TestEtapa1ProvidersOnboarding(unittest.TestCase):
    def test_etapa1_clean_state_and_onboarding(self):
        """Garante que a aplicação inicia limpa e exibe o assistente de onboarding."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            app = Application(Path(tmp_dir))

            # Deve começar sem nenhum provedor cadastrado (Clean Slate)
            providers = app.providers.list_providers()
            self.assertEqual(len(providers), 0)

            # O renderizador do painel de provedores deve incluir o wizard e dicas didáticas
            from kiros.ui.providers import render_providers_panel
            html = render_providers_panel(app, {})

            self.assertIn("Bem-vindo às Configurações do KIROS Studio", html)
            self.assertIn("Como pegar sua chave de API em 3 cliques", html)
            self.assertIn("Adobe Firefly", html)
            self.assertIn("ChatGPT", html)
            self.assertIn("Google Gemini", html)
            self.assertIn("Nenhum provedor configurado ainda", html)

    def test_etapa1_provider_router_fallback(self):
        """Garante que o ImageEngineRouter redireciona para um provedor ativo via Fallback."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            app = Application(Path(tmp_dir))

            # Adiciona um provedor ativo do tipo 'openai' (ChatGPT)
            app.providers.add_provider(
                provider_id='openai-chatgpt',
                provider_type='openai',
                name='ChatGPT (DALL-E 3)',
                model='dall-e-3',
                secret='sk-test-key-123',
                is_active=True
            )

            # Solicita recomendação de motor para tarefa de estúdio (onde a recomendação padrão seria 'firefly')
            res = app.router.resolve('camp-test-1', slide_context={'type': 'studio'})

            # Como 'firefly' não está ativo, deve cair no fallback e usar 'openai' que está ativo!
            self.assertEqual(res['provider'], 'openai')
            self.assertEqual(res['model'], 'dall-e-3')
            self.assertTrue(res.get('fallback_used'))
            self.assertIn('Fallback automático ativado', res['reason'])


if __name__ == '__main__':
    unittest.main()
