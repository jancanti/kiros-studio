import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from kiros.application import Application
from kiros.library import PRODUCT_FIELDS, VISUAL_FIELDS
from kiros.providers.mock import MockVision

# PNG mínimo determinístico; fixture técnica, não foto comercial nem imagem gerada.
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = Application(Path(self.tmp.name))
        self.lib = self.app.library
        self.lib.create_product('fixture', 'Produto de teste', source='fixture local')

    def proposal(self, value='vidro', protection='protected'):
        return self.lib.propose('product', 'fixture', {'material': {'value': value, 'protection': protection}}, 'edição manual')

    def reference(self, **changes):
        args = dict(product_id='fixture', origin='own', source_reference='fixture local', rights='confirmed', angle='front', quality=3)
        args.update(changes)
        return self.lib.add_reference(PNG, **args)

    def test_brand_approval_version_history_and_campaign_snapshot(self):
        v1 = self.lib.propose('brand', 'global', {'colors': 'verde', 'fonts': 'Georgia'}, 'guia recebido')
        self.assertEqual(self.lib.brand_for(), {})
        self.lib.approve(v1, 'Revisor')
        self.lib.override_brand('camp-a', {'colors': 'branco'}, 'briefing A')
        self.lib.override_brand('camp-b', {'fonts': 'Arial'}, 'briefing B')
        v2 = self.lib.propose('brand', 'global', {'colors': 'azul', 'fonts': 'Georgia'}, 'revisão')
        self.assertEqual(self.lib.brand_for()['colors'], 'verde')
        self.lib.approve(v2, 'Revisor')
        self.assertEqual(self.lib.brand_for()['colors'], 'azul')
        self.assertEqual(self.lib.brand_for('camp-a'), {'colors': 'branco', 'fonts': 'Georgia'})
        self.assertEqual(self.lib.brand_for('camp-b'), {'colors': 'verde', 'fonts': 'Arial'})
        old = self.lib.snapshot()['bible_versions'][0]
        self.assertEqual(json.loads(old['content'])['colors'], 'verde')
        self.assertEqual(old['approved_by'], 'Revisor')
        reopened = Application(Path(self.tmp.name)).library
        self.assertEqual(reopened.brand_for('camp-a'), self.lib.brand_for('camp-a'))
        self.assertEqual(len(reopened.snapshot()['bible_versions']), 2)

    def test_stale_and_repeated_approval_rejected(self):
        first = self.proposal()
        stale = self.proposal('metal')
        with self.assertRaises(ValueError):
            self.lib.approve(first, '')
        self.lib.approve(first, 'Revisor')
        for v in (first, stale, 10000):
            with self.assertRaises(ValueError):
                self.lib.approve(v, 'Revisor', True)
        self.assertEqual(sum(bool(v['approved_at']) for v in self.lib.snapshot()['bible_versions']), 1)

    def test_protected_needs_explicit_confirmation_and_critical_cannot_be_downgraded(self):
        self.lib.approve(self.proposal(), 'Revisor')
        changed = self.proposal('cerâmica', 'critical')
        for confirmation in (False, 'yes', 1):
            with self.assertRaises(ValueError):
                self.lib.approve(changed, 'Revisor', confirmation)
        self.lib.approve(changed, 'Revisor', True)
        for value, level in [('madeira', 'critical'), ('cerâmica', 'free')]:
            v = self.proposal(value, level)
            with self.assertRaisesRegex(ValueError, 'critical'):
                self.lib.approve(v, 'Revisor', True)
        removal = self.lib.propose('product', 'fixture', {'logo': {'value': 'KIROS', 'protection': 'critical'}}, 'manual')
        with self.assertRaisesRegex(ValueError, 'critical'):
            self.lib.approve(removal, 'Revisor', True)

    def test_free_edit_and_protected_removal(self):
        self.lib.approve(self.proposal(protection='free'), 'Revisor')
        self.lib.approve(self.proposal('cerâmica', 'protected'), 'Revisor')
        removal = self.lib.propose('product', 'fixture', {'shape': {'value': 'cilindro', 'protection': 'free'}}, 'manual')
        with self.assertRaisesRegex(ValueError, 'protected'):
            self.lib.approve(removal, 'Revisor')
        self.lib.approve(removal, 'Revisor', True)

    def test_product_stock_missing_zero_origin_and_history(self):
        self.assertIsNone(self.lib.snapshot()['products'][0]['stock'])
        self.lib.set_stock('fixture', 0, 'contagem física')
        self.lib.set_stock('fixture', 7, 'nova contagem')
        state = self.lib.snapshot()
        self.assertEqual([r['quantity'] for r in state['stock_history']], [0, 7])
        self.assertEqual(json.loads(state['stock_history'][0]['provenance'])['reference'], 'contagem física')
        for invalid in (-1, '1.5', True, '', '1000000000'):
            with self.assertRaises(ValueError):
                self.lib.set_stock('fixture', invalid, 'manual')
        for call in (lambda: self.lib.set_stock('missing', 1, 'manual'),
                     lambda: self.lib.set_stock('fixture', 1, ''),
                     lambda: self.lib.create_product('fixture', 'duplicado'),
                     lambda: self.lib.create_product('bad id', 'produto')):
            with self.assertRaises(ValueError):
                call()
        self.assertEqual(self.lib.snapshot()['products'][0]['stock'], 7)

    def test_csv_atomic_rejection_and_preserves_absent_revenue(self):
        header = 'product_id,date,quantity,revenue\n'
        good = header + 'fixture,2026-09-01,2,\nfixture,2026-09-02,0,0\n'
        self.assertEqual(self.lib.import_sales(good, 'exportação manual'), 2)
        before = self.lib.snapshot()
        self.assertEqual([r['revenue'] for r in before['sales']], [None, '0.00'])
        self.assertIsNone(before['products'][0]['stock'])
        invalid_rows = ['unknown,2026-09-01,1,2', 'fixture,2026-02-30,1,2',
                        'fixture,2026-09-01,,', 'fixture,2026-09-01,-1,2',
                        'fixture,2026-09-01,1,NaN', 'fixture,2026-09-01,1,1.999',
                        'fixture,2026-09-01,1,2,extra', 'fixture,2026-09-01,1',
                        'fixture,2026-09-01,1,=1+1']
        for row in invalid_rows:
            with self.assertRaises(ValueError, msg=row):
                self.lib.import_sales(header + 'fixture,2026-09-01,1,10\n' + row + '\n', 'arquivo inválido')
        for content, source in [(good, 'duplicado'), (header, 'vazio'), ('wrong\n', 'arquivo'), (good, '')]:
            with self.assertRaises(ValueError):
                self.lib.import_sales(content, source)
        self.assertEqual(self.lib.snapshot(), before)

    def test_reference_scope_task_quality_manual_and_rights(self):
        front = self.reference(quality=4)
        detail = self.reference(angle='detail', quality=5, origin='external')
        unknown = self.reference(angle='side', rights='unknown')
        campaign_a = self.reference(scope='campaign', campaign='a', angle='context')
        campaign_b = self.reference(scope='campaign', campaign='b')
        self.lib.create_product('other', 'Outro produto')
        other = self.reference(product_id='other')
        self.assertEqual(self.lib.reference_set('fixture', 'catalog')[0]['id'], front)
        self.assertEqual(self.lib.reference_set('fixture', 'label')[0]['id'], detail)
        self.assertEqual(self.lib.reference_set('fixture', 'lifestyle', 'a')[0]['id'], campaign_a)
        self.assertNotIn(campaign_b, [r['id'] for r in self.lib.reference_set('fixture', 'catalog', 'a')])
        self.assertEqual([r['id'] for r in self.lib.reference_set('fixture', 'catalog', manual_ids=[unknown, front])], [unknown, front])
        for ids in ([campaign_a], [other], [front, front], ['missing'], []):
            with self.assertRaises(ValueError):
                self.lib.reference_set('fixture', 'catalog', manual_ids=ids)
        rows = {r['id']: r for r in self.lib.snapshot()['visual_references']}
        for ref in (detail, unknown):
            self.assertEqual(rows[ref]['usage'], 'inspiration_only')
        self.assertEqual(rows[front]['usage'], 'commercial_reference')
        self.assertEqual(self.app.storage.get(rows[front]['asset_key']), PNG)
        visual = json.loads(rows[front]['analysis'])
        self.assertTrue(visual['simulated'])
        self.assertEqual(set(visual['attributes']), set(VISUAL_FIELDS))
        self.assertTrue(all(value is None for value in visual['attributes'].values()))

    def test_invalid_reference_rejected_before_storage(self):
        for changes in ({'scope':'campaign'}, {'campaign':'a'}, {'origin':'invented'},
                        {'quality':6}, {'angle':'bad'}, {'rights':'invented'},
                        {'source_reference':''}, {'product_id':'missing'}):
            with self.assertRaises(ValueError):
                self.reference(**changes)
        with self.assertRaises(ValueError):
            self.lib.add_reference(b'<html>not an image</html>', source_reference='teste')
        self.assertEqual(self.lib.snapshot()['visual_references'], [])
        self.assertEqual(list(self.app.storage.root.rglob('*')), [])

    def test_vision_contract_mock_proposal_never_official_and_injection(self):
        with self.assertRaises(ValueError):
            self.lib.analyze_product('fixture')
        for angle in ('front', 'side', 'detail'):
            self.reference(angle=angle)
        provider = Mock(wraps=MockVision())
        self.lib.vision = provider
        version = self.lib.analyze_product('fixture')
        provider.analyze_product.assert_called_once()
        self.assertEqual(len(provider.analyze_product.call_args[0][0]), 3)
        row = next(v for v in self.lib.snapshot()['bible_versions'] if v['id'] == version)
        self.assertIsNone(row['approved_at'])
        self.assertEqual(set(json.loads(row['content'])), set(PRODUCT_FIELDS))
        self.assertIn('"simulated": true', json.loads(row['provenance'])['reference'])
        provider.analyze_product.return_value = {'attributes': {}}
        with self.assertRaises(ValueError):
            self.lib.analyze_product('fixture')
        self.assertEqual(len(self.lib.snapshot()['bible_versions']), 1)


if __name__ == '__main__':
    unittest.main()
