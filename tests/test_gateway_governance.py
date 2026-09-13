"""Testes de governança e controle dinâmico do ExternalGateway."""
import tempfile
import unittest
from pathlib import Path

from kiros.application import Application
from kiros.infrastructure.security import Policy, ExternalGateway
from kiros.ui.providers import dispatch_provider_action, render_providers_panel


class GatewayGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)
        self.app = Application(self.data_dir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_policy_is_mock(self):
        policy = self.app.get_gateway_policy()
        self.assertEqual(policy['mode'], 'mock')
        self.assertFalse(policy['allow_paid'])
        self.assertFalse(policy['allow_publish'])

        # No modo mock, chamadas externas devem lançar PermissionError
        with self.assertRaises(PermissionError) as ctx:
            self.app.gateway.call(lambda: 'test', paid=False, approved=True)
        self.assertIn('bloqueadas no modo mock', str(ctx.exception))

    def test_update_gateway_policy_to_live(self):
        # Atualiza para modo Live
        res = dispatch_provider_action(
            self.app,
            'update_gateway_policy',
            {
                'provider_mode': 'live',
                'allow_paid_apis': '1',
                'allow_publish': '0',
            },
        )
        self.assertIn('saved=1', res)

        policy = self.app.get_gateway_policy()
        self.assertEqual(policy['mode'], 'live')
        self.assertTrue(policy['allow_paid'])
        self.assertFalse(policy['allow_publish'])

        # No modo Live com paid=False e approved=True, a chamada deve passar no gateway
        res_call = self.app.gateway.call(lambda: 'network_response_ok', paid=False, approved=True)
        self.assertEqual(res_call, 'network_response_ok')

    def test_persistence_across_app_reloads(self):
        # Altera política e verifica persistência no SQLite
        self.app.update_gateway_policy(mode='live', allow_paid=True, allow_publish=True)

        # Recarrega a aplicação no mesmo diretório
        reloaded_app = Application(self.data_dir)
        policy = reloaded_app.get_gateway_policy()
        self.assertEqual(policy['mode'], 'live')
        self.assertTrue(policy['allow_paid'])
        self.assertTrue(policy['allow_publish'])

    def test_render_providers_panel_contains_gateway_control(self):
        html = render_providers_panel(self.app, {})
        self.assertIn('Modo de Conexão do Estúdio', html)
        self.assertIn('action="/api/providers/update_gateway_policy"', html)
        self.assertIn('name="provider_mode"', html)


if __name__ == '__main__':
    unittest.main()
