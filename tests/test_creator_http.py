"""Testes HTTP para Creative Director, briefing híbrido e banco de ideias (M03, Seções 9, 11-16)."""
import http.client
from html.parser import HTMLParser
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from kiros.__main__ import make_server


class CreatorHTTPTests(unittest.TestCase):
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
        return self.request('/api/creator/' + action, urlencode(values), **kwargs)

    def test_creator_page_renders_components(self):
        # 1. Rota /criar carrega com 200 e exibe seções principais
        status, page, headers = self.request('/criar')
        self.assertEqual(status, 200)
        self.assertIn('Creative Director', page)
        self.assertIn('Briefing Híbrido', page)
        self.assertIn('Banco de Ideias', page)
        self.assertIn('Conteúdo Adjacente e Pontes de Marca', page)
        self.assertIn('Datas Prioritárias (2–3 Meses Antes)', page)

        # Exibe os 6 pilares iniciais
        for pillar in ('Produtos', 'Lifestyle', 'Marca', 'Educativo', 'Relacionamento', 'Comercial'):
            self.assertIn(pillar, page)

    def test_interpret_briefing_flow(self):
        # 2. Submete briefing livre
        briefing_text = "Quero lançar uma nova vela de alecrim e flor de laranjeira para um ritual matinal acolhedor."
        status, _, headers = self.post('interpret_briefing', {
            'briefing_text': briefing_text,
            'custom_objective': '',
        })
        self.assertEqual(status, 303)
        loc = headers.get('Location', '')
        self.assertIn('/criar?', loc)
        self.assertIn('briefing_done=1', loc)
        self.assertIn('primary_obj=lan', loc)  # lançamento

        # Carrega a página após o redirect
        status, page, _ = self.request(loc)
        self.assertEqual(status, 200)
        self.assertIn('Briefing Estruturado', page)
        self.assertIn('Diretrizes da Campanha', page)
        self.assertIn('LANÇAMENTO', page)
        self.assertIn('Salvar como Ideia no Banco', page)

    def test_idea_bank_add_pin_reject_and_limit_via_http(self):
        # 3. Adiciona ideia via POST
        status, _, headers = self.post('add_idea', {
            'title': 'Sessão de Aromaterapia Noturna',
            'concept': 'Vídeo curto mostrando o ritual de acender a vela antes de ler um livro',
            'pillar': 'lifestyle',
            'is_pinned': '1',
        })
        self.assertEqual(status, 303)

        status, page, _ = self.request('/criar')
        self.assertEqual(status, 200)
        self.assertIn('Sessão de Aromaterapia Noturna', page)
        self.assertIn('FIXADA', page)
        self.assertIn('1/5 ativas', page)

        # Obtém o ID da ideia através da página
        import re
        match = re.search(r'name="idea_id"\s+value="([a-f0-9]+)"', page)
        self.assertIsNotNone(match)
        idea_id = match.group(1)

        # Desafixa a ideia
        status, _, headers = self.post('pin_idea', {
            'idea_id': idea_id,
            'pin': '0',
        })
        self.assertEqual(status, 303)

        status, page, _ = self.request('/criar')
        self.assertNotIn('FIXADA', page)

        # Rejeita a ideia com motivo
        status, _, headers = self.post('reject_idea', {
            'idea_id': idea_id,
            'reason': 'Abordagem muito genérica de relaxamento',
        })
        self.assertEqual(status, 303)

        status, page, _ = self.request('/criar')
        self.assertIn('REJECTED', page)
        self.assertIn('muito genérica', page)
        self.assertIn('0/5 ativas', page)

    def test_security_csrf_origin_and_content_type(self):
        # 4. Requisição sem Origin ou com Origin inválido é bloqueada com 403
        status, _, _ = self.post('add_idea', {'title': 'Hack'}, origin=False)
        self.assertEqual(status, 403)

        # Content-Type inválido é recusado com 415
        status, _, _ = self.request(
            '/api/creator/add_idea',
            body='{"title": "Hack"}',
            kind='application/json',
        )
        self.assertEqual(status, 415)


if __name__ == '__main__':
    unittest.main()

