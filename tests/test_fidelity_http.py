"""Testes HTTP para Fidelidade de Produto, Comparação Visual de Versões e Aprendizados (M06)."""
import http.client
from pathlib import Path
import re
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from kiros.__main__ import make_server


class FidelityHTTPTests(unittest.TestCase):
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

    def _create_approved_campaign_with_versions(self):
        # 1. Cria campanha
        _, _, headers = self.post('create', {
            'title': 'Campanha HTTP M06',
            'briefing_text': 'Lançamento de vela aromática artesanal de alecrim.',
            'custom_objective': 'lançamento',
            'approval_mode': 'minimal',
        })
        cid = re.search(r'campaign_id=([a-f0-9]+)', headers.get('Location', '')).group(1)

        # 2. Aprova
        self.post('approve', {'campaign_id': cid, 'approver': 'Diretoria'})

        # 3. Enfileira e roda worker para gerar v1
        self.post('queue', {'campaign_id': cid})
        self.post('run_worker', {'campaign_id': cid})

        # 4. Extrai slide_id
        _, page, _ = self.request(f'/conteudo?campaign_id={cid}')
        slide_id = re.search(r'name="slide_id"\s+value="([a-f0-9]+)"', page).group(1)

        # 5. Gera v2 via intervenção localizada
        self.post('regenerate_slide', {
            'campaign_id': cid,
            'slide_id': slide_id,
            'new_prompt': 'Prompt v2 com iluminação difusa natural',
        })
        self.post('run_worker', {'campaign_id': cid})

        # 6. Gera v3 com outro motor
        self.post('regenerate_slide', {
            'campaign_id': cid,
            'slide_id': slide_id,
            'new_prompt': 'Prompt v3 em madeira escura',
            'engine_override': 'openai:dall-e-3',
        })
        self.post('run_worker', {'campaign_id': cid})

        return cid, slide_id

    def test_side_by_side_comparison_view_and_differences(self):
        # 1. Valida painel de comparação visual lado a lado de até 3 versões (Seção 54)
        cid, slide_id = self._create_approved_campaign_with_versions()

        # Extrai os IDs das versões do HTML
        _, page, _ = self.request(f'/conteudo?campaign_id={cid}')
        version_ids = re.findall(r'name="compare_versions"\s+value="([a-f0-9]+)"', page)
        self.assertGreaterEqual(len(version_ids), 3)

        v1_id, v2_id, v3_id = version_ids[:3]

        # Acessa /conteudo com o parâmetro de comparação
        status, comp_page, _ = self.request(f'/conteudo?campaign_id={cid}&compare_versions={v1_id},{v2_id},{v3_id}')
        self.assertEqual(status, 200)

        self.assertIn('Comparação Lado a Lado (3 versões de até 3)', comp_page)
        self.assertIn('v1', comp_page)
        self.assertIn('v2', comp_page)
        self.assertIn('v3', comp_page)
        self.assertIn('Diferenças Detectadas na Comparação:', comp_page)
        self.assertIn('Variação de Custo:', comp_page)
        self.assertIn('Escolher como Ativa (choose)', comp_page)
        self.assertIn('Usar como Base (use_as_base)', comp_page)
        self.assertIn('Registrar Aprendizado (record_learning)', comp_page)

    def test_choose_and_restore_version_flow(self):
        # 2. Testa ações choose e restore preservando histórico completo (Seção 53, 54, 80)
        cid, slide_id = self._create_approved_campaign_with_versions()

        _, page, _ = self.request(f'/conteudo?campaign_id={cid}')
        version_ids = re.findall(r'name="compare_versions"\s+value="([a-f0-9]+)"', page)
        v1_id, v2_id = version_ids[0], version_ids[1]

        # Escolhe v1 como ativa
        status, _, headers = self.post('choose_version', {
            'campaign_id': cid,
            'version_id': v1_id,
        })
        self.assertEqual(status, 303)
        self.assertIn('definida+como+ativa', headers.get('Location', ''))

        # Restaura v2
        status, _, headers = self.post('restore_version', {
            'campaign_id': cid,
            'version_id': v2_id,
        })
        self.assertEqual(status, 303)
        self.assertIn('restaurada+sem+apagar', headers.get('Location', ''))

    def test_use_as_base_flow(self):
        # 3. Testa usar versão como base (Seção 54)
        cid, slide_id = self._create_approved_campaign_with_versions()

        _, page, _ = self.request(f'/conteudo?campaign_id={cid}')
        v1_id = re.findall(r'name="compare_versions"\s+value="([a-f0-9]+)"', page)[0]

        status, _, headers = self.post('use_as_base', {
            'campaign_id': cid,
            'version_id': v1_id,
            'new_prompt': 'Novo prompt refinado a partir da v1',
        })
        self.assertEqual(status, 303)
        self.assertIn('baseada+na+vers', headers.get('Location', ''))

    def test_record_learning_flow(self):
        # 4. Testa registro de aprendizado (Seção 54, 80)
        cid, slide_id = self._create_approved_campaign_with_versions()

        _, page, _ = self.request(f'/conteudo?campaign_id={cid}')
        v1_id = re.findall(r'name="compare_versions"\s+value="([a-f0-9]+)"', page)[0]

        note = 'Composição clean reforçou a identidade da marca'
        status, _, _ = self.post('record_learning', {
            'campaign_id': cid,
            'version_id': v1_id,
            'learning_note': note,
        })
        self.assertEqual(status, 303)

        _, page_after, _ = self.request(f'/conteudo?campaign_id={cid}')
        self.assertIn('Aprendizados Registrados (Seção 80):', page_after)
        self.assertIn(note, page_after)

    def test_set_fidelity_config_flow(self):
        # 5. Testa configuração de modo e threshold de fidelidade (Seção 27)
        cid, slide_id = self._create_approved_campaign_with_versions()

        status, _, headers = self.post('set_fidelity_config', {
            'campaign_id': cid,
            'fidelity_mode': 'auto_regenerate',
            'fidelity_threshold': '92',
        })
        self.assertEqual(status, 303)

        _, page, _ = self.request(f'/conteudo?campaign_id={cid}')
        self.assertIn('AUTO_REGENERATE', page)
        self.assertIn('92/100', page)


if __name__ == '__main__':
    unittest.main()

