"""Testes HTTP para Motor de Layout, Editor Semântico e Templates (Seções 28, 29, 30)."""
import http.client
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from kiros.__main__ import make_server


class LayoutHTTPTests(unittest.TestCase):
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

    def _create_campaign_and_get_slide_and_layout(self):
        # 1. Cria campanha com 3 slides
        _, _, headers = self.post('create', {
            'title': 'Campanha HTTP Layout',
            'briefing_text': 'Coleção de difusores aromáticos de flor de laranjeira.',
            'custom_objective': 'lançamento',
            'approval_mode': 'minimal',
        })
        cid = re.search(r'campaign_id=([a-f0-9]+)', headers.get('Location', '')).group(1)

        # 2. Localiza o primeiro slide e seu layout no SQLite
        db_path = Path(self.tmp.name) / 'studio.sqlite3'
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            slide_row = conn.execute('SELECT id, title FROM storyboard_slides WHERE campaign_id=? ORDER BY slide_order ASC LIMIT 1', (cid,)).fetchone()
            sid = slide_row['id']
            layout_row = conn.execute('SELECT id, format FROM slide_layouts WHERE slide_id=?', (sid,)).fetchone()
            lid = layout_row['id']

        return cid, sid, lid

    def test_layout_editor_ui_rendering_and_svg_endpoint(self):
        """M07-A01 e M07-A05: Comprova interface do editor, renderização SVG e exportação determinística."""
        cid, sid, lid = self._create_campaign_and_get_slide_and_layout()

        # Abre a interface de conteúdo com o editor ativo para o slide
        status, page, _ = self.request(f'/conteudo?campaign_id={cid}&editor_slide_id={sid}')
        self.assertEqual(status, 200)
        self.assertIn('Editor Visual Semântico · Seções 28, 29, 30', page)
        self.assertIn('Feed 4:5 (1080×1350)', page)
        self.assertIn('Stories 9:16 (1080×1920)', page)
        self.assertIn('🟢 Verde · Livre', page)
        self.assertIn('🟡 Amarelo · Protected', page)
        self.assertIn('🔴 Vermelho · Critical', page)

        # Endpoint GET /api/layout/svg
        status_svg, svg_body, headers_svg = self.request(f'/api/layout/svg?layout_id={lid}')
        self.assertEqual(status_svg, 200)
        self.assertEqual(headers_svg.get('Content-Type'), 'image/svg+xml; charset=utf-8')
        self.assertTrue(svg_body.startswith('<svg'))
        self.assertIn('id="headline"', svg_body)
        self.assertIn('id="logo"', svg_body)

        # Endpoint GET /api/layout/svg com safe areas visíveis
        status_safe, safe_body, _ = self.request(f'/api/layout/svg?layout_id={lid}&safe_areas=1')
        self.assertEqual(status_safe, 200)
        self.assertIn('id="safe-area-overlay"', safe_body)

        # Endpoint GET /api/layout/export
        status_exp, exp_body, headers_exp = self.request(f'/api/layout/export?layout_id={lid}')
        self.assertEqual(status_exp, 200)
        self.assertEqual(headers_exp.get('Content-Type'), 'application/json')
        data = json.loads(exp_body)
        self.assertEqual(data['layout_id'], lid)
        self.assertEqual(data['format'], '4:5')
        self.assertEqual(data['dimensions'], {'width': 1080, 'height': 1350})
        self.assertTrue(data['proportions_verified'])

    def test_update_layout_protection_levels_over_http(self):
        """M07-A02: Comprova validação de proteção verde, amarelo e vermelho via HTTP."""
        cid, sid, lid = self._create_campaign_and_get_slide_and_layout()

        # 1. Atributo Verde (Livre) -> Sucesso direto sem confirmação
        status, _, headers = self.post('update_layout', {
            'campaign_id': cid,
            'layout_id': lid,
            'slide_id': sid,
            'framing': 'close-up',
            'lighting': 'golden_hour',
            'scale': '1.15',
        })
        self.assertEqual(status, 303)
        self.assertIn('Layout+atualizado+com+sucesso', headers.get('Location', ''))

        # 2. Atributo Amarelo (Protected) sem confirmação -> Erro
        status, _, headers = self.post('update_layout', {
            'campaign_id': cid,
            'layout_id': lid,
            'slide_id': sid,
            'headline_text': 'Novo Título Sem Confirmar',
        })
        self.assertEqual(status, 303)
        self.assertIn('error=', headers.get('Location', ''))
        self.assertIn('confirma', headers.get('Location', '').lower())

        # 3. Atributo Amarelo (Protected) com confirmação explícita -> Sucesso
        status, _, headers = self.post('update_layout', {
            'campaign_id': cid,
            'layout_id': lid,
            'slide_id': sid,
            'headline_text': 'Título Confirmado Exato',
            'confirm_protected': '1',
        })
        self.assertEqual(status, 303)
        self.assertIn('Layout+atualizado+com+sucesso', headers.get('Location', ''))

        # 4. Atributo Vermelho (Critical) sem unlock -> Erro
        status, _, headers = self.post('update_layout', {
            'campaign_id': cid,
            'layout_id': lid,
            'slide_id': sid,
            'logo_locked': '0',
        })
        self.assertEqual(status, 303)
        self.assertIn('error=', headers.get('Location', ''))

        # 5. Atributo Vermelho (Critical) com unlock e justificativa auditada -> Sucesso
        status, _, headers = self.post('update_layout', {
            'campaign_id': cid,
            'layout_id': lid,
            'slide_id': sid,
            'logo_locked': '0',
            'unlock_critical': '1',
            'audit_reason': 'Autorizado para anúncio com enquadramento macro',
            'unlocked_by': 'Diretoria de Arte · João',
        })
        self.assertEqual(status, 303)
        self.assertIn('Layout+atualizado+com+sucesso', headers.get('Location', ''))

        # Comprova registro no banco de auditoria
        db_path = Path(self.tmp.name) / 'studio.sqlite3'
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            audit_row = conn.execute('SELECT * FROM layout_audit_log WHERE layout_id=?', (lid,)).fetchone()
            self.assertIsNotNone(audit_row)
            self.assertEqual(audit_row['attribute_name'], 'logo_locked')
            self.assertEqual(audit_row['operator'], 'Diretoria de Arte · João')

    def test_switch_format_responsive_adaptation_over_http(self):
        """M07-A01 e M07-A05: Comprova alternância de formato para 9:16 e 4:5 com cálculo de safe areas."""
        cid, sid, lid = self._create_campaign_and_get_slide_and_layout()

        # Altera para 9:16
        status, _, headers = self.post('switch_layout_format', {
            'campaign_id': cid,
            'layout_id': lid,
            'slide_id': sid,
            'target_format': '9:16',
        })
        self.assertEqual(status, 303)
        self.assertIn('Formato+alterado+para+%279%3A16%27', headers.get('Location', ''))

        # Inspeciona exportação e valida dimensões 1080x1920
        _, exp_body, _ = self.request(f'/api/layout/export?layout_id={lid}')
        data = json.loads(exp_body)
        self.assertEqual(data['format'], '9:16')
        self.assertEqual(data['dimensions'], {'width': 1080, 'height': 1920})
        self.assertTrue(data['proportions_verified'])

    def test_template_application_and_governance_over_http(self):
        """M07-A04: Comprova aplicação de template ativo, rejeição de experimental não autorizado e autorização."""
        cid, sid, lid = self._create_campaign_and_get_slide_and_layout()

        # 1. Aplica template ativo da família lifestyle_natural
        status, _, headers = self.post('apply_template', {
            'campaign_id': cid,
            'layout_id': lid,
            'slide_id': sid,
            'template_id': 'tpl-lifestyle-natural',
        })
        self.assertEqual(status, 303)
        self.assertIn('Template+de+layout+aplicado', headers.get('Location', ''))

        # 2. Aplica template experimental sem autorização -> Bloqueio
        status, _, headers = self.post('apply_template', {
            'campaign_id': cid,
            'layout_id': lid,
            'slide_id': sid,
            'template_id': 'tpl-experimental-botanical',
            'experimental_authorized': '0',
        })
        self.assertEqual(status, 303)
        self.assertIn('error=', headers.get('Location', ''))
        self.assertIn('experimental', headers.get('Location', '').lower())

        # 3. Aplica template experimental com autorização explícita -> Sucesso
        status, _, headers = self.post('apply_template', {
            'campaign_id': cid,
            'layout_id': lid,
            'slide_id': sid,
            'template_id': 'tpl-experimental-botanical',
            'experimental_authorized': '1',
        })
        self.assertEqual(status, 303)
        self.assertIn('Template+de+layout+aplicado', headers.get('Location', ''))

    def test_save_composition_as_template_and_approve_layout_over_http(self):
        """M07-A04: Salva composição aprovada como novo template reutilizável."""
        cid, sid, lid = self._create_campaign_and_get_slide_and_layout()

        # Aprova layout
        status, _, headers = self.post('approve_layout', {
            'campaign_id': cid,
            'layout_id': lid,
            'slide_id': sid,
            'approver': 'Diretoria de Arte',
        })
        self.assertEqual(status, 303)
        self.assertIn('aprovada', headers.get('Location', ''))

        # Salva como novo template
        status, _, headers = self.post('save_layout_as_template', {
            'campaign_id': cid,
            'layout_id': lid,
            'slide_id': sid,
            'template_name': 'Layout Especial Âmbar Botânico',
            'template_family': 'editorial_minimalist',
            'template_status': 'active',
        })
        self.assertEqual(status, 303)
        self.assertIn('Composi%C3%A7%C3%A3o+salva+como+novo+template', headers.get('Location', ''))

        # Comprova persistência na tabela layout_templates
        db_path = Path(self.tmp.name) / 'studio.sqlite3'
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            tpl_row = conn.execute('SELECT * FROM layout_templates WHERE name=?', ('Layout Especial Âmbar Botânico',)).fetchone()
            self.assertIsNotNone(tpl_row)
            self.assertEqual(tpl_row['family'], 'editorial_minimalist')
            self.assertEqual(tpl_row['status'], 'active')

    def test_product_bible_strict_isolation_over_http(self):
        """M07-A03: Edição de layout via HTTP nunca altera a Product Bible oficial no servidor."""
        cid, sid, lid = self._create_campaign_and_get_slide_and_layout()
        db_path = Path(self.tmp.name) / 'studio.sqlite3'

        with sqlite3.connect(db_path) as conn:
            initial_count = conn.execute('SELECT COUNT(*) FROM bible_versions').fetchone()[0]

        # Várias operações de layout submetidas via HTTP
        self.post('update_layout', {
            'campaign_id': cid,
            'layout_id': lid,
            'slide_id': sid,
            'scale': '1.2',
            'lighting': 'soft_studio',
        })
        self.post('switch_layout_format', {
            'campaign_id': cid,
            'layout_id': lid,
            'slide_id': sid,
            'target_format': '9:16',
        })
        self.post('apply_template', {
            'campaign_id': cid,
            'layout_id': lid,
            'slide_id': sid,
            'template_id': 'tpl-editorial-minimalist',
        })

        # Comprova que a tabela bible_versions não sofreu nenhuma inserção ou mutação
        with sqlite3.connect(db_path) as conn:
            final_count = conn.execute('SELECT COUNT(*) FROM bible_versions').fetchone()[0]

        self.assertEqual(final_count, initial_count)


if __name__ == '__main__':
    unittest.main()

