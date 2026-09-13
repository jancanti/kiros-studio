"""Testes HTTP para a tela e rotas de gerenciamento de providers (M02-A01, Seção 8)."""
import http.client
from html.parser import HTMLParser
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from kiros.__main__ import make_server


class FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.inputs = []

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        if 'id' in attr_dict:
            self.ids.append(attr_dict['id'])
        if tag == 'input' and 'name' in attr_dict:
            self.inputs.append(attr_dict['name'])


class ProvidersHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.server = make_server(self.tmp.name, 0)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(self, path, body=None, kind='application/x-www-form-urlencoded', origin=True, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        req_headers = {'Content-Type': kind}
        if origin:
            req_headers['Origin'] = f'http://127.0.0.1:{self.port}'
        if headers:
            req_headers.update(headers)
        conn.request('GET' if body is None else 'POST', path, body, req_headers)
        res = conn.getresponse()
        result = res.status, res.read().decode('utf-8'), dict(res.getheaders())
        conn.close()
        return result

    def post(self, action, values, **kwargs):
        return self.request('/api/providers/' + action, urlencode(values), **kwargs)

    def test_providers_ui_and_secret_never_returned(self):
        # 1. Tela de configurações contém a seção de providers
        status, page, _ = self.request('/configuracoes')
        self.assertEqual(status, 200)
        self.assertIn('Provedores Configurados', page)
        self.assertIn('Adicionar ou Atualizar Provedor', page)

        secret_key = 'super-private-api-key-999888'

        # 2. Cadastro de provider via POST
        status, _, headers = self.post('save', {
            'provider_id': 'gemini-prod',
            'name': 'Google Gemini Produção',
            'provider_type': 'gemini',
            'model': 'imagen-3.0-generate-002',
            'secret': secret_key,
            'is_active': '1',
        })
        self.assertEqual(status, 303)
        self.assertIn('/configuracoes?tab=providers', headers.get('Location', ''))

        # 3. Recarrega a página: o provedor aparece, mas o segredo NUNCA aparece
        status, page, _ = self.request('/configuracoes')
        self.assertEqual(status, 200)
        self.assertIn('Google Gemini Produção', page)
        self.assertIn('imagen-3.0-generate-002', page)
        self.assertIn('••••••••', page)
        self.assertNotIn(secret_key, page)

        # 4. Teste de conexão (no modo mock, retorna recusa segura e latência registrada)
        status, _, headers = self.post('test_connection', {'provider_id': 'gemini-prod'})
        self.assertEqual(status, 303)
        self.assertIn('test_done=1', headers.get('Location', ''))

        # Segredo não vazou na URL de redirecionamento
        self.assertNotIn(secret_key, headers.get('Location', ''))

        # 5. Toggle para desativar
        status, _, headers = self.post('toggle', {'provider_id': 'gemini-prod', 'is_active': '0'})
        self.assertEqual(status, 303)

        status, page, _ = self.request('/configuracoes')
        self.assertIn('Inativo', page)

        # 6. Exclusão
        status, _, headers = self.post('delete', {'provider_id': 'gemini-prod'})
        self.assertEqual(status, 303)

        status, page, _ = self.request('/configuracoes')
        self.assertNotIn('Google Gemini Produção', page)

    def test_security_csrf_origin_and_content_type(self):
        # Origem não permitida é bloqueada
        status, _, _ = self.post('save', {'provider_id': 'hacked'}, origin=False)
        self.assertEqual(status, 403)

        # Content-Type inválido é recusado com 415
        status, _, _ = self.request(
            '/api/providers/save',
            body='{"provider_id": "bad"}',
            kind='application/json',
        )
        self.assertEqual(status, 415)

    def test_configuracoes_ui_and_same_origin_form_submission(self):
        # 1. Cabeçalho Referrer-Policy deve ser same-origin
        status, page, headers = self.request('/configuracoes')
        self.assertEqual(status, 200)
        self.assertEqual(headers.get('Referrer-Policy'), 'same-origin')

        # 2. Estilos do formulário e botão no CSS e formulário inline
        status_css, css, _ = self.request('/style.css')
        self.assertEqual(status_css, 200)
        self.assertIn('form.inline-form', css)
        self.assertIn('white-space:nowrap', css)
        self.assertIn('min-width:max-content', css)
        self.assertIn('flex-shrink:0', css)
        self.assertIn('flex:1;min-width:140px', page)

        # 3. Submissão via formulário padrão com Referer (sem Origin) é aceita
        payload = urlencode({'workspace_name': 'Estúdio Teste Referer'})
        status, _, resp_headers = self.request(
            '/api/preferences',
            body=payload,
            origin=False,
            headers={'Referer': f'http://127.0.0.1:{self.port}/configuracoes'},
        )
        self.assertEqual(status, 303)
        self.assertIn('/configuracoes?saved=1', resp_headers.get('Location', ''))

        # 4. Submissão via formulário padrão com Sec-Fetch-Site same-origin (sem Origin/Referer) é aceita
        payload = urlencode({'workspace_name': 'Estúdio Teste SecFetch'})
        status, _, resp_headers = self.request(
            '/api/preferences',
            body=payload,
            origin=False,
            headers={'Sec-Fetch-Site': 'same-origin'},
        )
        self.assertEqual(status, 303)
        self.assertIn('/configuracoes?saved=1', resp_headers.get('Location', ''))

        # 5. Requisição com Sec-Fetch-Site cross-site é bloqueada com 403
        status, _, _ = self.request(
            '/api/preferences',
            body=payload,
            origin=False,
            headers={'Sec-Fetch-Site': 'cross-site'},
        )
        self.assertEqual(status, 403)


if __name__ == '__main__':
    unittest.main()

