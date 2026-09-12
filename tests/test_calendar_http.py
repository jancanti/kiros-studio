"""Testes de Integração HTTP para Calendário Editorial e Publicação no Instagram (M09-A01 a M09-A06)."""
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

from kiros.__main__ import make_server
from kiros.core.contracts import Provenance


class CalendarHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)

        # Encontra porta livre
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            self.port = s.getsockname()[1]

        self.server = make_server(self.data_dir, port=self.port)
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        time.sleep(0.1)

        from kiros.application import Application
        self.app = Application(self.data_dir)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.temp_dir.cleanup()

    def _post(self, path: str, data: dict, follow_redirects: bool = False, headers: dict = None):
        encoded = urllib.parse.urlencode(data).encode('utf-8')
        default_headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Host': f'127.0.0.1:{self.port}',
            'Origin': f'http://127.0.0.1:{self.port}',
        }
        if headers:
            default_headers.update(headers)
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=encoded,
            headers=default_headers,
            method='POST',
        )
        if not follow_redirects:
            class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    return None
            opener = urllib.request.build_opener(NoRedirectHandler)
            try:
                return opener.open(req)
            except urllib.error.HTTPError as err:
                return err
        return urllib.request.urlopen(req)

    def _get(self, path: str, headers: dict = None):
        default_headers = {'Host': f'127.0.0.1:{self.port}'}
        if headers:
            default_headers.update(headers)
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            headers=default_headers,
        )
        return urllib.request.urlopen(req)

    def test_calendar_page_get_renders_clean_html_and_wcag(self):
        """M09-A01: Rota /calendario renderiza tipografia Rubik/Inter, WCAG, CSP e limites."""
        resp = self._get('/calendario')
        self.assertEqual(resp.status, 200)
        body = resp.read().decode('utf-8')

        # Verificação de estrutura e WCAG
        self.assertIn('<title>Calendário · KIROS Studio</title>', body)
        self.assertIn('Pular para o conteúdo', body)
        self.assertIn('aria-current="page"', body)
        self.assertIn('Calendário Editorial', body)
        self.assertIn('Frequência e Restrições de Saturação', body)
        self.assertIn('Meta Graph API', body)
        self.assertIn('@kiros.aromas', body)
        self.assertIn('Rubik', body)
        self.assertIn('Inter', body)

        # Cabeçalhos de Segurança
        headers = dict(resp.getheaders())
        self.assertIn('Content-Security-Policy', headers)
        self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])
        self.assertEqual(headers.get('X-Content-Type-Options'), 'nosniff')

    def test_calendar_entries_get_json_api(self):
        """M09-A01: Endpoint GET /api/calendar/entries retorna JSON com lista de itens."""
        # Cria uma entrada via serviço
        self.app.calendar.create_entry(
            title='Velas de Lavanda e Âmbar',
            content_type='feed',
            pillar='lifestyle',
        )

        resp = self._get('/api/calendar/entries')
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.headers.get('Content-Type'), 'application/json')
        data = json.loads(resp.read().decode('utf-8'))
        self.assertIsInstance(data, list)
        self.assertTrue(len(data) >= 1)
        self.assertEqual(data[0]['title'], 'Velas de Lavanda e Âmbar')
        self.assertEqual(data[0]['pillar'], 'lifestyle')

    def test_create_entry_and_preferences_post(self):
        """M09-A01: Salva limites de frequência e cria nova entrada via POST."""
        # Salva preferências
        resp_pref = self._post('/api/calendar/save_preferences', {
            'max_posts_per_week': '5',
            'min_hours_between_posts': '36',
            'saturation_threshold_per_pillar_per_week': '2',
            'preferred_days': 'seg,qua,sex',
        })
        self.assertEqual(resp_pref.status, 303)
        self.assertIn('/calendario', resp_pref.headers.get('Location'))

        # Cria entrada
        resp_entry = self._post('/api/calendar/create_entry', {
            'title': 'Difusor de Varetas Alecrim',
            'content_type': 'feed',
            'pillar': 'lancamento',
            'priority': 'medium',
            'notes': 'Post focado no aroma herbal relaxante.',
        })
        self.assertEqual(resp_entry.status, 303)
        location = resp_entry.headers.get('Location')
        self.assertIn('created_entry', location)

        # Confere que aparece na página
        page_resp = self._get('/calendario')
        page_body = page_resp.read().decode('utf-8')
        self.assertIn('Difusor de Varetas Alecrim', page_body)
        self.assertIn('LANCAMENTO', page_body)

    def test_recommend_time_and_manual_decision_http(self):
        """M09-A02: Recomenda horário e registra decisão manual com 'Manual sempre vence'."""
        entry = self.app.calendar.create_entry(
            title='Ritual de Bem-Estar Noturno',
            content_type='feed',
            pillar='lifestyle',
        )

        # 1. Dispara recomendação do Creative Director
        resp_rec = self._post('/api/calendar/recommend_time', {'entry_id': entry.id})
        self.assertEqual(resp_rec.status, 303)

        # Confere na página que a recomendação com camadas e confiança é renderizada
        page_resp = self._get('/calendario')
        page_body = page_resp.read().decode('utf-8')
        self.assertIn('Recomendação Inteligente do Creative Director', page_body)
        self.assertIn('Confiança', page_body)
        self.assertIn('Estimativa estatística com base nos dados disponíveis', page_body)

        # 2. Usuário escolhe horário manual ("Manual sempre vence")
        custom_time = '2026-11-28T20:30:00+00:00'
        resp_manual = self._post('/api/calendar/set_time_decision', {
            'entry_id': entry.id,
            'selected_time': custom_time,
            'accept_recommendation': '0',
        })
        self.assertEqual(resp_manual.status, 303)

        # Confere que o horário manual venceu
        updated_entry = self.app.calendar.get_entry(entry.id)
        self.assertEqual(updated_entry.selected_time, custom_time)
        self.assertFalse(updated_entry.time_accepted)

        page_manual = self._get('/calendario').read().decode('utf-8')
        self.assertIn('Horário manual definido (Manual venceu)', page_manual)

    def test_publish_with_explicit_confirmation_and_refusal_without(self):
        """M09-A04, M09-A05, Seção 79: Recusa sem confirmação explícita e aprovação com confirmação."""
        entry = self.app.calendar.create_entry(
            title='Velas de Bergamota',
            content_type='feed',
            pillar='institucional',
        )

        # 1. Tentativa sem confirmação explícita
        resp_refused = self._post('/api/calendar/publish_or_schedule', {
            'entry_id': entry.id,
            'confirmed_by': 'Operador KIROS',
            'explicit_confirmation': '0',  # Não marcou confirmação
        })
        self.assertEqual(resp_refused.status, 303)
        location_refused = resp_refused.headers.get('Location')
        self.assertIn('error', location_refused)
        self.assertIn('confirma%C3%A7%C3%A3o+expl%C3%ADcita', location_refused)

        # 2. Publicação com confirmação explícita
        resp_ok = self._post('/api/calendar/publish_or_schedule', {
            'entry_id': entry.id,
            'confirmed_by': 'Operador KIROS',
            'explicit_confirmation': '1',  # Marcou o checkbox formal
        })
        self.assertEqual(resp_ok.status, 303)
        location_ok = resp_ok.headers.get('Location')
        self.assertIn('published_id', location_ok)
        self.assertIn('msg', location_ok)

        # Confere status publicado
        published_entry = self.app.calendar.get_entry(entry.id)
        self.assertEqual(published_entry.status, 'published')

    def test_security_csrf_and_origin_protection(self):
        """M09-A06, Seção 70: Validação de Host, Origin e proteção contra CSRF."""
        # 1. Host malicioso
        try:
            resp_bad_host = self._get('/calendario', headers={'Host': 'evil-attacker.com'})
            self.assertEqual(resp_bad_host.status, 403)
        except urllib.error.HTTPError as err:
            self.assertEqual(err.code, 403)

        # 2. Origin cross-site em POST
        resp_bad_origin = self._post(
            '/api/calendar/create_entry',
            {'title': 'Hack attempt'},
            headers={'Origin': 'http://evil-attacker.com'},
        )
        self.assertEqual(resp_bad_origin.status, 403)


if __name__ == '__main__':
    unittest.main()

