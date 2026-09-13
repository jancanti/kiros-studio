"""Testes das credenciais do Instagram (Meta Graph API) em /configuracoes."""
import tempfile
import unittest
from pathlib import Path

from kiros.application import Application
from kiros.ui.providers import dispatch_provider_action, render_providers_panel


class InstagramCredentialsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)
        self.app = Application(self.data_dir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_and_retrieve_instagram_credentials(self):
        # 1. Estado inicial
        creds = self.app.publisher.get_credentials()
        self.assertFalse(creds['has_token'])
        self.assertEqual(creds['account_id'], '')

        # 2. Salva credenciais via publisher
        self.app.publisher.save_credentials(
            account_id='17841409988776655',
            access_token='EAAB_test_token_live_access_secret_123',
            username='usekiros',
            app_secret='secret_hash_456',
        )

        # 3. Recupera credenciais e verifica preview mascarado
        updated = self.app.publisher.get_credentials()
        self.assertTrue(updated['has_token'])
        self.assertEqual(updated['account_id'], '17841409988776655')
        self.assertEqual(updated['username'], 'usekiros')
        self.assertIn('••••••••', updated['token_preview'])
        self.assertNotIn('EAAB_test_token_live_access_secret_123', updated['token_preview'])

        # 4. Limpa credenciais
        self.app.publisher.clear_credentials()
        cleared = self.app.publisher.get_credentials()
        self.assertFalse(cleared['has_token'])
        self.assertIsNone(cleared['access_token'])

    def test_dispatch_save_and_clear_instagram(self):
        # POST save_instagram
        res = dispatch_provider_action(
            self.app,
            'save_instagram',
            {
                'account_id': '1784140001',
                'username': '@usekiros',
                'access_token': 'EAAB_token_via_dispatch',
                'app_secret': '',
            },
        )
        self.assertIn('saved=1', res)
        creds = self.app.publisher.get_credentials()
        self.assertTrue(creds['has_token'])
        self.assertEqual(creds['username'], 'usekiros')

        # POST clear_instagram
        res_clear = dispatch_provider_action(self.app, 'clear_instagram', {})
        self.assertIn('removidas', res_clear)
        self.assertFalse(self.app.publisher.get_credentials()['has_token'])

    def test_render_providers_panel_contains_instagram_form(self):
        html = render_providers_panel(self.app, {})
        self.assertIn('Credenciais do Instagram', html)
        self.assertIn('action="/api/providers/save_instagram"', html)
        self.assertIn('ig_account_id', html)
        self.assertIn('ig_token', html)


if __name__ == '__main__':
    unittest.main()
