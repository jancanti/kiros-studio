"""Testes HTTP para Fila de Execução, Monitoramento, Diagnóstico e Intervenção Localizada (M05)."""
import http.client
from pathlib import Path
import re
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from kiros.__main__ import make_server


class ExecutionHTTPTests(unittest.TestCase):
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
        return self.request('/api/campaigns/' + action, urlencode(values), **kwargs)

    def _create_and_approve_campaign(self):
        # Cria campanha
        _, _, headers = self.post('create', {
            'title': 'Campanha Teste Execução HTTP',
            'briefing_text': 'Lançamento de difusor aromático de varetas.',
            'custom_objective': 'lançamento',
            'approval_mode': 'minimal',
        })
        cid = re.search(r'campaign_id=([a-f0-9]+)', headers.get('Location', '')).group(1)

        # Aprova
        self.post('approve', {'campaign_id': cid, 'approver': 'Diretor de Arte'})
        return cid

    def test_queue_execution_and_monitoring_panel(self):
        # 1. Enfileira execução e valida painel de monitoramento (Seção 50, 67)
        cid = self._create_and_approve_campaign()

        status, _, headers = self.post('queue', {'campaign_id': cid})
        self.assertEqual(status, 303)

        status, page, _ = self.request(f'/conteudo?campaign_id={cid}')
        self.assertEqual(status, 200)

        # Painel de monitoramento da geração
        self.assertIn('Monitoramento da Geração', page)
        self.assertIn('Modo de Monitoramento:', page)
        self.assertIn('SUPERVISED', page)
        self.assertIn('Processar Fila (Worker Local)', page)
        self.assertIn('Pausar Execução', page)
        self.assertIn('Custo Incorrido (Concluído):', page)
        self.assertIn('Risco de Cobrança em Voo:', page)
        self.assertIn('Orçamento Poupado ao Cancelar:', page)

    def test_monitoring_mode_change_flow(self):
        # 2. Altera modo de monitoramento (Seção 50)
        cid = self._create_and_approve_campaign()
        self.post('queue', {'campaign_id': cid})

        status, _, _ = self.post('set_monitoring_mode', {
            'campaign_id': cid,
            'monitoring_mode': 'detailed',
        })
        self.assertEqual(status, 303)

        _, page, _ = self.request(f'/conteudo?campaign_id={cid}')
        self.assertIn('DETAILED', page)

    def test_pause_and_resume_execution_via_http(self):
        # 3. Pausa e retoma execução (Seção 52)
        cid = self._create_and_approve_campaign()
        self.post('queue', {'campaign_id': cid})

        # Pausar
        status, _, _ = self.post('pause', {'campaign_id': cid})
        self.assertEqual(status, 303)
        _, page_paused, _ = self.request(f'/conteudo?campaign_id={cid}')
        self.assertIn('PAUSED', page_paused)
        self.assertIn('Retomar Execução', page_paused)

        # Retomar
        status, _, _ = self.post('resume', {'campaign_id': cid})
        self.assertEqual(status, 303)
        _, page_resumed, _ = self.request(f'/conteudo?campaign_id={cid}')
        self.assertIn('Pausar Execução', page_resumed)

    def test_worker_processing_and_versions_preservation(self):
        # 4. Processa fila com worker local e verifica versões preservadas (Seção 52)
        cid = self._create_and_approve_campaign()
        self.post('queue', {'campaign_id': cid})

        # Executa worker
        status, _, _ = self.post('run_worker', {'campaign_id': cid})
        self.assertEqual(status, 303)

        _, page, _ = self.request(f'/conteudo?campaign_id={cid}')
        self.assertIn('COMPLETED', page)
        self.assertIn('Versões Preservadas:', page)
        self.assertIn('asset-', page)

    def test_localized_slide_regeneration_via_http(self):
        # 5. Intervenção localizada: regenera somente um slide (Seção 51)
        cid = self._create_and_approve_campaign()
        self.post('queue', {'campaign_id': cid})
        self.post('run_worker', {'campaign_id': cid})

        # Extrai slide_id
        _, page, _ = self.request(f'/conteudo?campaign_id={cid}')
        slide_match = re.search(r'name="slide_id"\s+value="([a-f0-9]+)"', page)
        self.assertIsNotNone(slide_match)
        slide_id = slide_match.group(1)

        # Regenera somente este slide
        status, _, _ = self.post('regenerate_slide', {
            'campaign_id': cid,
            'slide_id': slide_id,
            'new_prompt': 'Prompt aperfeiçoado com iluminação dourada e reflexos suaves.',
            'engine_override': 'gemini:imagen-3.0-generate-002',
        })
        self.assertEqual(status, 303)

        # Processa o novo trabalho
        self.post('run_worker', {'campaign_id': cid})

        _, page_after, _ = self.request(f'/conteudo?campaign_id={cid}')
        # Slide agora possui versão 2 preservada (Seção 52: Nunca apagar versões)
        self.assertIn('v2:', page_after)

    def test_slide_cancellation_and_impact_disclosure(self):
        # 6. Cancelamento de slide com demonstrativo financeiro (Seção 52)
        cid = self._create_and_approve_campaign()
        self.post('queue', {'campaign_id': cid})

        _, page, _ = self.request(f'/conteudo?campaign_id={cid}')
        slide_id = re.search(r'name="slide_id"\s+value="([a-f0-9]+)"', page).group(1)

        status, _, headers = self.post('cancel_slide', {
            'campaign_id': cid,
            'slide_id': slide_id,
        })
        self.assertEqual(status, 303)
        loc = headers.get('Location', '')
        self.assertIn('Slide+cancelado', loc)


if __name__ == '__main__':
    unittest.main()

