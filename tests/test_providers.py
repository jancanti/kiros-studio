"""Testes unitários para provedores, adaptadores e proteção de segredos (M02-A01, M02-A02, M02-A03, M02-A07)."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from kiros.application import Application
from kiros.infrastructure.security import ExternalGateway, Policy, Secret
from kiros.providers.catalog import (
    OFFICIAL_CATALOG,
    get_model_cost,
    validate_model,
    validate_provider_type,
)
from kiros.providers.engines import (
    GeminiImageEngine,
    OpenAIImageEngine,
    FireflyImageEngine,
    CustomImageProvider,
    ProviderError,
    _sanitize_error_message,
)
from kiros.providers.manager import ProviderManager


class ProvidersTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = Application(Path(self.tmp.name))
        self.pm = self.app.providers

    def test_official_catalog_and_model_validation(self):
        # Modelos oficiais vigentes em 2026-09-12
        self.assertEqual(validate_model('gemini', 'imagen-3.0-generate-002'), 'imagen-3.0-generate-002')
        self.assertEqual(validate_model('gemini', 'imagen-3.0-fast-generate-001'), 'imagen-3.0-fast-generate-001')
        self.assertEqual(validate_model('openai', 'dall-e-3'), 'dall-e-3')
        self.assertEqual(validate_model('openai', 'dall-e-2'), 'dall-e-2')
        self.assertEqual(validate_model('firefly', 'firefly-image-3'), 'firefly-image-3')
        self.assertEqual(validate_model('firefly', 'firefly-image-2'), 'firefly-image-2')

        # Modelos inexistentes ou presumidos devem ser terminantemente rejeitados
        for provider, invalid in [
            ('gemini', 'gemini-image-v1'),
            ('gemini', 'dall-e-3'),
            ('gemini', 'imagen-2'),
            ('openai', 'dall-e-4'),
            ('openai', 'midjourney'),
            ('firefly', 'firefly-v9'),
        ]:
            with self.assertRaises(ValueError):
                validate_model(provider, invalid)

        # Provedor customizado aceita identificador não vazio
        self.assertEqual(validate_model('custom', 'my-flux-lora-v1'), 'my-flux-lora-v1')
        with self.assertRaises(ValueError):
            validate_model('custom', '   ')

    def test_provider_registration_toggle_and_secret_protection(self):
        secret_key = 'sk-secret-key-that-must-never-leak-12345'
        pid = self.pm.add_provider(
            provider_id='gemini-main',
            provider_type='gemini',
            name='Gemini Oficial',
            model='imagen-3.0-generate-002',
            secret=secret_key,
            is_active=True,
        )
        self.assertEqual(pid, 'gemini-main')

        # Frontend e listagens NUNCA devem expor o segredo
        prov_view = self.pm.get_provider('gemini-main')
        self.assertNotIn(secret_key, repr(prov_view) + str(prov_view))
        self.assertTrue(prov_view['has_secret'])
        self.assertEqual(prov_view['secret_preview'], '••••••••')
        self.assertNotIn('secret', prov_view)

        list_view = self.pm.list_providers()
        self.assertEqual(len(list_view), 1)
        self.assertNotIn(secret_key, repr(list_view) + str(list_view))

        # Ativação e desativação
        self.pm.toggle_provider('gemini-main', False)
        self.assertFalse(self.pm.get_provider('gemini-main')['is_active'])
        self.assertEqual(len(self.pm.list_providers(active_only=True)), 0)

        self.pm.toggle_provider('gemini-main', True)
        self.assertTrue(self.pm.get_provider('gemini-main')['is_active'])
        self.assertEqual(len(self.pm.list_providers(active_only=True)), 1)

        # Atualização sem enviar segredo preserva o segredo existente
        self.pm.update_provider('gemini-main', name='Gemini Atualizado', secret='')
        internal = self.pm.get_provider('gemini-main', include_secret=True)
        self.assertEqual(internal['name'], 'Gemini Atualizado')
        self.assertEqual(internal['secret'], secret_key)

    def test_sanitization_removes_secrets_from_error_messages(self):
        key = 'ai-secret-key-xyz-987'
        raw_error = f"HTTP 401: Unauthorized for key={key} and Bearer {key} from provider"
        sanitized = _sanitize_error_message(raw_error, secret=key)
        self.assertNotIn(key, sanitized)
        self.assertIn('[REDACTED]', sanitized)

    def test_deterministic_contract_gemini(self):
        # Mocks determinísticos cobrindo sucesso, erro, timeout, credencial inválida e indisponibilidade
        gw = ExternalGateway(Policy('live', allow_paid=True))

        # 1. Sucesso
        def transport_ok(req, timeout):
            return {'status': 200, 'data': {'predictions': ['base64image']}, 'latency_ms': 42}

        engine = GeminiImageEngine(gw, model='imagen-3.0-generate-002', transport=transport_ok)
        conn = engine.test_connection()
        self.assertEqual(conn['status'], 'ok')
        self.assertEqual(conn['latency_ms'], 42)
        gen = engine.generate({'prompt': 'Frasco de vela em vidro âmbar', 'approved': True})
        self.assertTrue(gen.startswith('gemini:imagen-3.0-generate-002'))

        # 2. Erro 400 Bad Request
        def transport_400(req, timeout):
            return {'status': 400, 'error': 'Bad Request: invalid aspect ratio', 'latency_ms': 15}

        engine_400 = GeminiImageEngine(gw, model='imagen-3.0-generate-002', transport=transport_400)
        conn_400 = engine_400.test_connection()
        self.assertEqual(conn_400['status'], 'error')
        self.assertIn('Bad Request', conn_400['message'])

        # 3. Timeout
        def transport_timeout(req, timeout):
            return {'status': 503, 'error': 'Erro de conexão/timeout: TimeoutError', 'latency_ms': 10000}

        engine_to = GeminiImageEngine(gw, model='imagen-3.0-generate-002', transport=transport_timeout)
        conn_to = engine_to.test_connection()
        self.assertEqual(conn_to['status'], 'error')
        self.assertIn('timeout', conn_to['message'].lower())

        # 4. Credencial inválida (401)
        secret_key = 'fake-gemini-key'
        def transport_401(req, timeout):
            return {'status': 401, 'error': f'HTTP 401: Unauthorized key={secret_key}', 'latency_ms': 30}

        engine_401 = GeminiImageEngine(gw, model='imagen-3.0-generate-002', secret=secret_key, transport=transport_401)
        conn_401 = engine_401.test_connection()
        self.assertEqual(conn_401['status'], 'error')
        self.assertNotIn(secret_key, conn_401['message'])

        # 5. Indisponibilidade (503)
        def transport_503(req, timeout):
            return {'status': 503, 'error': 'HTTP 503: Service Unavailable', 'latency_ms': 120}

        engine_503 = GeminiImageEngine(gw, model='imagen-3.0-generate-002', transport=transport_503)
        conn_503 = engine_503.test_connection()
        self.assertEqual(conn_503['status'], 'error')
        self.assertIn('503', conn_503['message'])

    def test_deterministic_contract_openai(self):
        gw = ExternalGateway(Policy('live', allow_paid=True))

        def transport_ok(req, timeout):
            return {'status': 200, 'data': {'data': [{'url': 'http://simulated.test'}]}, 'latency_ms': 55}

        engine = OpenAIImageEngine(gw, model='dall-e-3', transport=transport_ok)
        conn = engine.test_connection()
        self.assertEqual(conn['status'], 'ok')
        self.assertEqual(conn['latency_ms'], 55)

        def transport_401(req, timeout):
            return {'status': 401, 'error': 'HTTP 401: Invalid API Key', 'latency_ms': 25}

        engine_401 = OpenAIImageEngine(gw, model='dall-e-3', transport=transport_401)
        self.assertEqual(engine_401.test_connection()['status'], 'error')

    def test_deterministic_contract_firefly(self):
        gw = ExternalGateway(Policy('live', allow_paid=True))

        def transport_ok(req, timeout):
            return {'status': 200, 'data': {'outputs': [{'image': {'url': 'http://simulated'}}]}, 'latency_ms': 60}

        engine = FireflyImageEngine(gw, model='firefly-image-3', transport=transport_ok)
        conn = engine.test_connection()
        self.assertEqual(conn['status'], 'ok')

        def transport_timeout(req, timeout):
            return {'status': 503, 'error': 'Erro de conexão/timeout: URLError', 'latency_ms': 5000}

        engine_to = FireflyImageEngine(gw, model='firefly-image-3', transport=transport_timeout)
        self.assertEqual(engine_to.test_connection()['status'], 'error')

    def test_deterministic_contract_custom_provider(self):
        gw = ExternalGateway(Policy('live', allow_paid=True))

        # Endpoint é obrigatório para custom
        with self.assertRaises(ValueError):
            CustomImageProvider(gw, model='flux-1', endpoint='')

        def transport_ok(req, timeout):
            return {'status': 200, 'data': {'output': 'ok'}, 'latency_ms': 20}

        custom = CustomImageProvider(gw, model='flux-1', endpoint='http://127.0.0.1:9999/v1/generate', transport=transport_ok)
        conn = custom.test_connection()
        self.assertEqual(conn['status'], 'ok')
        self.assertEqual(conn['latency_ms'], 20)

    def test_central_policy_blocks_egress_in_mock_mode_for_all_adapters(self):
        # M02-A07: Política central bloqueia egress do produto em mock
        mock_gw = ExternalGateway(Policy('mock', allow_paid=False))

        gemini = GeminiImageEngine(mock_gw, model='imagen-3.0-generate-002')
        openai = OpenAIImageEngine(mock_gw, model='dall-e-3')
        firefly = FireflyImageEngine(mock_gw, model='firefly-image-3')
        custom = CustomImageProvider(mock_gw, model='local-model', endpoint='http://127.0.0.1:8000/gen')

        for engine in (gemini, openai, firefly, custom):
            with self.assertRaises(PermissionError):
                engine.test_connection()
            with self.assertRaises(PermissionError):
                engine.test_simple()
            with self.assertRaises(PermissionError):
                engine.generate({'prompt': 'teste', 'approved': True})

    def test_manager_records_test_logs(self):
        pid = self.pm.add_provider('prov-log-test', 'gemini', 'Gemini Log', 'imagen-3.0-generate-002')
        # No modo mock, o test_connection é recusado pelo gateway e registrado nos logs
        res = self.pm.test_connection(pid)
        self.assertEqual(res['status'], 'error')
        self.assertIn('mock', res['message'])

        logs = self.pm.get_test_logs(pid)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]['provider_id'], pid)
        self.assertEqual(logs[0]['test_type'], 'connection')
        self.assertEqual(logs[0]['status'], 'error')


if __name__ == '__main__':
    unittest.main()
