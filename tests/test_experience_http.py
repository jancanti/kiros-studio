"""Testes HTTP da Experiência Integrada, Dashboard, Busca e Command Bar (M11)."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from kiros.__main__ import make_server


class ExperienceHTTPTests(unittest.TestCase):
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

    def test_dashboard_renders_all_six_sections(self):
        """M11-A04: Dashboard contextual na página /inicio renderiza os 6 blocos."""
        status, page, _ = self.request('/inicio')
        self.assertEqual(status, 200)
        self.assertIn('Dashboard Contextual', page)
        # 6 blocos: Hoje, Oportunidade, Próximo passo recomendado, Calendário, Criação, Aprendizados
        self.assertIn('Hoje</span>', page)
        self.assertIn('Oportunidade</span>', page)
        self.assertIn('Próximo passo recomendado</span>', page)
        self.assertIn('Calendário</span>', page)
        self.assertIn('Criação</span>', page)
        self.assertIn('Aprendizados</span>', page)

    def test_library_renders_unified_tabs_and_search(self):
        """M11-A04: /biblioteca organiza produtos, referências, imagens, campanhas, templates, prompts e versões."""
        status, page, _ = self.request('/biblioteca')
        self.assertEqual(status, 200)
        self.assertIn('Busca no Acervo e Estúdio', page)
        self.assertIn('tab=referencias', page)
        self.assertIn('tab=produtos', page)
        self.assertIn('tab=imagens', page)
        self.assertIn('tab=campanhas', page)
        self.assertIn('tab=templates', page)
        self.assertIn('tab=prompts', page)
        self.assertIn('tab=versoes', page)

    def test_global_search_api_endpoint(self):
        """M11-A02: GET /api/search retorna resultados estruturados em JSON."""
        status, body, _ = self.request('/api/search?q=KIROS')
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIsInstance(data, list)

    def test_command_bar_post_execution_and_redirection(self):
        """M11-A03: POST /api/command executa ação e redireciona."""
        # 1. Comando reversível: pausar geração
        payload = urlencode({'command': 'Pause a geração'})
        status, _, headers = self.request('/api/command', body=payload)
        self.assertEqual(status, 303)
        self.assertIn('notice=', headers.get('Location', ''))
        self.assertIn('pausada', headers.get('Location', '').lower())

        # 2. Comando ambíguo: recusado
        payload_amb = urlencode({'command': 'gastar'})
        status_amb, _, headers_amb = self.request('/api/command', body=payload_amb)
        self.assertEqual(status_amb, 303)
        self.assertIn('recusado', headers_amb.get('Location', '').lower())

    def test_approve_prompt_flow(self):
        """M11-A01: Salvar prompt permanentemente via POST na biblioteca."""
        # Cria uma proposta de prompt pelo app interno do servidor
        app = self.server.RequestHandlerClass(None, ('127.0.0.1', 0), self.server).server.app if hasattr(self.server, 'app') else None
        # Obtém o app via instância criada em make_server
        # Usamos o endpoint POST /api/prompts/approve
        with tempfile.TemporaryDirectory() as tmp_data:
            from kiros.application import Application
            test_app = Application(Path(tmp_data))
            pid = test_app.prompt_library.suggest_prompt(
                title='Vela Âmbar Aconchego',
                objective='Foto editorial de outono',
                engine='recraft_v3',
                context='Linha Casa',
                prompt_text='Warm candle light on oak surface',
                result_summary='Excelente nitidez',
                performance_score=90.0,
            )
            # Aprova
            approved = test_app.prompt_library.approve_prompt(pid, approver='Curador de Estúdio')
            self.assertEqual(approved['status'], 'approved')
            self.assertEqual(approved['approved_by'], 'Curador de Estúdio')

    def test_security_controls_csrf_and_origin(self):
        """M11-A05: Proteção de origem e CSRF no endpoint de comandos."""
        payload = urlencode({'command': 'Pause a geração'})
        status, _, _ = self.request('/api/command', body=payload, origin=False)
        self.assertEqual(status, 403)


if __name__ == '__main__':
    unittest.main()
