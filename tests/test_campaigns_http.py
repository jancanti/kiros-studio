"""Testes HTTP para Campanhas, Storyboard, Pipeline e Tela de Aprovação (M04, Seções 10, 23, 31, 56, 66, 75)."""
import http.client
from pathlib import Path
import re
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from kiros.__main__ import make_server


class CampaignsHTTPTests(unittest.TestCase):
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

    def test_campaigns_page_renders_hub(self):
        # 1. Rota /conteudo carrega com 200 e exibe o hub de campanhas
        status, page, _ = self.request('/conteudo')
        self.assertEqual(status, 200)
        self.assertIn('Campanhas e Storyboard', page)
        self.assertIn('Conteúdo', page)
        self.assertIn('Planejamento visual, storyboard', page)
        self.assertIn('Novo Projeto', page)
        self.assertIn('Construir Campanha e Storyboard', page)

    def test_create_campaign_flow_and_approval_screen_fields(self):
        # 2. Submete criação de nova campanha via POST
        status, _, headers = self.post('create', {
            'title': 'Coleção Outono Aromático',
            'briefing_text': 'Lançamento de nova vela aromática artesanal com aroma amadeirado e pavio ecológico.',
            'custom_objective': 'lançamento',
            'approval_mode': 'minimal',
        })
        self.assertEqual(status, 303)
        loc = headers.get('Location', '')
        self.assertIn('/conteudo?campaign_id=', loc)

        # Extrai o campaign_id do location
        match = re.search(r'campaign_id=([a-f0-9]+)', loc)
        self.assertIsNotNone(match)
        cid = match.group(1)

        # Carrega a Tela de Aprovação (Seção 75)
        status, page, _ = self.request(loc)
        self.assertEqual(status, 200)

        # Valida campos obrigatórios da Seção 75
        self.assertIn('Tela de Aprovação · Seção 75', page)
        self.assertIn('Coleção Outono Aromático', page)
        self.assertIn('Objetivo:', page)
        self.assertIn('LANÇAMENTO', page)
        self.assertIn('Conceito e Briefing:', page)
        self.assertIn('Gerações Estimadas:', page)
        self.assertIn('Custo Estimado Total:', page)
        self.assertIn('Nível de Confiança:', page)
        self.assertIn('Storyboard da Campanha', page)
        self.assertIn('Pipeline de Execução', page)
        self.assertIn('Aprovar Execução', page)
        self.assertIn('Cancelar Campanha', page)

    def test_localized_editing_and_material_change_flow(self):
        # 3. Cria campanha inicial
        _, _, headers = self.post('create', {
            'title': 'Campanha Teste Edição',
            'briefing_text': 'Teste de edição de pipeline e storyboard.',
            'custom_objective': 'awareness',
            'approval_mode': 'minimal',
        })
        loc = headers.get('Location', '')
        cid = re.search(r'campaign_id=([a-f0-9]+)', loc).group(1)

        # Carrega página para extrair um step_id do pipeline
        _, page, _ = self.request(f'/conteudo?campaign_id={cid}')
        step_match = re.search(r'name="step_id"\s+value="([a-f0-9]+)"', page)
        self.assertIsNotNone(step_match)
        step_id = step_match.group(1)

        # Aprova a execução do plano v1
        status, _, headers = self.post('approve', {
            'campaign_id': cid,
            'approver': 'Diretor de Arte',
        })
        self.assertEqual(status, 303)

        # Confirma que está aprovado
        _, page_appr, _ = self.request(f'/conteudo?campaign_id={cid}')
        self.assertIn('Aprovado', page_appr)
        self.assertIn('Enfileirar Execução na Fila', page_appr)

        # Realiza uma edição localizada no pipeline: alteração material!
        status, _, headers = self.post('update_step', {
            'campaign_id': cid,
            'step_id': step_id,
            'name': 'Geração Rápida com Fast',
            'provider_id': 'gemini',
            'model_id': 'imagen-3.0-fast-generate-001',
        })
        self.assertEqual(status, 303)

        # Confirma que a aprovação foi invalidada e o botão de re-aprovar aparece
        _, page_inval, _ = self.request(f'/conteudo?campaign_id={cid}')
        self.assertIn('Aprovar Execução', page_inval)
        self.assertNotIn('Enfileirar Execução na Fila', page_inval)

    def test_execution_without_approval_refused_via_http(self):
        # 4. Tentar enfileirar sem aprovação retorna aviso de erro amigável
        _, _, headers = self.post('create', {
            'title': 'Campanha Não Aprovada',
            'briefing_text': 'Tentativa direta de envio para a fila.',
        })
        loc = headers.get('Location', '')
        cid = re.search(r'campaign_id=([a-f0-9]+)', loc).group(1)

        # Envia POST direto para queue
        status, _, headers = self.post('queue', {'campaign_id': cid})
        self.assertEqual(status, 303)
        loc_err = headers.get('Location', '')
        self.assertIn('error=', loc_err)

        _, page_err, _ = self.request(loc_err)
        self.assertIn('Execução recusada', page_err)

    def test_slide_addition_and_engine_override_via_http(self):
        # 5. Adiciona novo slide e atualiza motor
        _, _, headers = self.post('create', {
            'title': 'Campanha Multi-Slide',
            'briefing_text': 'Fotografia de velas para catálogo.',
        })
        cid = re.search(r'campaign_id=([a-f0-9]+)', loc := headers.get('Location', '')).group(1)

        # Adiciona slide 4
        status, _, _ = self.post('add_slide', {
            'campaign_id': cid,
            'title': 'Slide 4: Vista Aérea dos Frascos',
            'visual_prompt': 'Vista superior de velas acesas em bandeja de mármore.',
            'framing': 'overhead',
            'caption_draft': 'Composição refinada para o seu lavabo.',
            'engine_override': 'openai:dall-e-3',
        })
        self.assertEqual(status, 303)

        _, page, _ = self.request(f'/conteudo?campaign_id={cid}')
        self.assertIn('Slide 4: Vista Aérea dos Frascos', page)
        self.assertIn('openai:dall-e-3', page)
        self.assertIn('Storyboard da Campanha (4 slides)', page)

    def test_cancel_campaign_flow(self):
        # 6. Cancelar campanha
        _, _, headers = self.post('create', {
            'title': 'Campanha para Cancelar',
            'briefing_text': 'Projeto experimental descartado.',
        })
        cid = re.search(r'campaign_id=([a-f0-9]+)', headers.get('Location', '')).group(1)

        status, _, _ = self.post('cancel', {'campaign_id': cid})
        self.assertEqual(status, 303)

        _, page, _ = self.request(f'/conteudo?campaign_id={cid}')
        self.assertIn('CANCELLED', page)

    def test_security_controls_origin_and_content_type(self):
        # 7. Segurança: recusa Origin forjado e Content-Type incompatível
        status, _, _ = self.post('create', {'title': 'Teste CSRF'}, origin=False, headers={'Origin': 'http://malicious.evil'})
        self.assertEqual(status, 403)

        status, _, _ = self.post('create', {'title': 'Teste JSON'}, kind='application/json')
        self.assertEqual(status, 415)


if __name__ == '__main__':
    unittest.main()
