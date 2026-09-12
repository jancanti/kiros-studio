import json
import http.client
from html.parser import HTMLParser
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import urlencode
from kiros.__main__ import make_server
from kiros.application import Application
from test_library import PNG


class FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.labels = [], []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'label' and 'for' in attrs:
            self.labels.append(attrs['for'])


class LibraryHTTPTests(unittest.TestCase):
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

    def request(self, path, body=None, kind='application/x-www-form-urlencoded', origin=True):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        headers = {'Content-Type': kind}
        if origin:
            headers['Origin'] = f'http://127.0.0.1:{self.port}'
        connection.request('GET' if body is None else 'POST', path, body, headers)
        response = connection.getresponse()
        result = response.status, response.read(), dict(response.getheaders())
        connection.close()
        return result

    def post(self, action, values):
        response = self.request('/api/library/' + action, urlencode(values))
        self.assertEqual(response[0], 303)
        self.assertTrue(response[2]['Location'].endswith('?saved=1'), response)
        return response

    def multipart(self, values, files):
        boundary = 'kiros-test-boundary'
        body = b''
        for name, value in values.items():
            body += f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        for name, (filename, value) in files.items():
            body += f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + value + b'\r\n'
        return body + f'--{boundary}--\r\n'.encode(), 'multipart/form-data; boundary=' + boundary

    def test_brand_product_csv_photo_analysis_and_reopen(self):
        self.post('brand', {'brand_colors':'Verde', 'source':'guia local'})
        lib = Application(Path(self.tmp.name)).library
        version = lib.snapshot()['bible_versions'][0]['id']
        self.assertEqual(lib.brand_for(), {})
        self.post('approve', {'version_id':version, 'approver':'Revisor local'})
        self.post('override', {'campaign':'teste', 'override_colors':'Branco', 'source':'briefing local'})
        self.post('product', {'product_id':'teste', 'name':'<script>Teste</script>', 'stock':'', 'source':'cadastro local'})
        self.post('stock', {'product_id':'teste', 'quantity':'0', 'source':'contagem local'})
        body, kind = self.multipart({'source':'exportação'}, {'csv':('vendas.csv', b'product_id,date,quantity,revenue\nteste,2026-09-01,2,\n')})
        self.assertEqual(self.request('/api/library/sales', body, kind)[2]['Location'], '/marca?saved=1')
        for angle in ('front', 'side', 'detail'):
            body, kind = self.multipart({'product_id':'teste', 'scope':'permanent', 'origin':'unknown', 'source_reference':'fixture técnica', 'rights':'unknown', 'angle':angle, 'quality':'3'}, {'photo':('../../ignored.png', PNG)})
            self.assertEqual(self.request('/api/library/reference', body, kind)[2]['Location'], '/biblioteca?saved=1')
        self.post('analyze', {'product_id':'teste'})
        reopened = Application(Path(self.tmp.name)).library
        state = reopened.snapshot()
        self.assertEqual(reopened.brand_for()['colors'], 'Verde')
        self.assertEqual(reopened.brand_for('teste')['colors'], 'Branco')
        self.assertEqual(state['products'][0]['stock'], 0)
        self.assertIsNone(state['sales'][0]['revenue'])
        self.assertEqual(len(state['bible_versions']), 2)
        self.assertIsNone(state['bible_versions'][-1]['approved_at'])
        asset = self.request('/assets/' + state['visual_references'][0]['id'])
        self.assertEqual(asset[1], PNG)
        self.assertEqual(asset[2]['Content-Type'], 'image/png')
        for route in ('/marca', '/biblioteca?product_id=teste&task=label'):
            response = self.request(route)
            page = response[1].decode()
            self.assertEqual(response[0], 200)
            self.assertNotIn('<script>Teste</script>', page)
            self.assertIn('&lt;script&gt;Teste&lt;/script&gt;', page)
            self.assertIn('simulação local', page)
            parser = FormParser()
            parser.feed(page)
            self.assertEqual(len(parser.ids), len(set(parser.ids)), 'IDs devem ser únicos')
            self.assertTrue(set(parser.labels) <= set(parser.ids))
        self.assertIn('inspiration_only', self.request('/biblioteca')[1].decode())
        self.assertEqual(self.request('/assets/../../ignored.png')[0], 404)

    def test_invalid_http_upload_csv_csrf_and_duplicate_fields_preserve_state(self):
        self.post('product', {'product_id':'teste', 'name':'Produto', 'source':'local'})
        library = Application(Path(self.tmp.name)).library
        before = library.snapshot()
        response = self.request('/api/library/stock', urlencode({'product_id':'teste','quantity':3,'source':'local'}), origin=False)
        self.assertEqual(response[0], 403)
        for action, body, kind in [
            ('stock', b'product_id=teste&quantity=1&quantity=2&source=x', 'application/x-www-form-urlencoded'),
            ('reference', *self.multipart({'source_reference':'local'}, {'photo':('bad.png', b'not an image')})),
            ('sales', *self.multipart({'source':'local'}, {'csv':('bad.csv', b'product_id,date,quantity,revenue\nteste,2026-09-01,1,10\nmissing,2026-09-01,2,3\n')})),
            ('sales', *self.multipart({'source':'local'}, {'csv':('bad.csv', b'\xff')})),
            ('reference', b'bad multipart', 'multipart/form-data; boundary=missing')]:
            response = self.request('/api/library/' + action, body, kind)
            self.assertEqual(response[0], 303)
            self.assertIn('?error=', response[2]['Location'])
            self.assertEqual(library.snapshot(), before)
        self.assertEqual(self.request('/api/library/product', '{}', 'application/json')[0], 415)


if __name__ == '__main__':
    unittest.main()
