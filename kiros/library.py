"""Marca e acervo local. Escritas oficiais são versões aprovadas, nunca updates de conteúdo."""
import csv
import hashlib
import io
import json
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import uuid4
from kiros.core.contracts import Provenance

BRAND_FIELDS = ('logo', 'variants', 'fonts', 'colors', 'photography', 'architecture',
                'decoration', 'materials', 'palette', 'composition', 'avoid_list',
                'approved_references', 'information')
PRODUCT_FIELDS = ('shape', 'proportion', 'material', 'glass', 'cap', 'label', 'logo', 'colors', 'packaging')
VISUAL_FIELDS = ('lighting', 'composition', 'materials', 'palette', 'architecture',
                 'framing', 'atmosphere', 'camera_distance', 'photography')
ANGLES = ('front', 'side', 'back', 'top', 'detail', 'context')
TASKS = {'catalog': ('front', 'side'), 'label': ('detail', 'front'),
         'lifestyle': ('context', 'front'), 'packaging': ('back', 'side')}


def text(value, label='Valor', limit=4000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'{label}: preencha até {limit} caracteres.')
    return value.strip()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value):
        raise ValueError('Identificador: use letras, números, hífen ou sublinhado (até 80).')
    return value


def integer(value):
    if isinstance(value, bool) or not re.fullmatch(r'[0-9]{1,9}', str(value)):
        raise ValueError('Quantidade deve ser um inteiro não negativo de até 9 dígitos.')
    return int(value)


def provenance(source, reference):
    return json.dumps(asdict(Provenance(source, text(reference, 'Origem'),
                                       datetime.now(timezone.utc).isoformat())), ensure_ascii=False)


class Library:
    def __init__(self, database, storage, vision):
        self.database, self.storage, self.vision = database, storage, vision

    @contextmanager
    def connection(self):
        with sqlite3.connect(self.database.path) as db:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('BEGIN IMMEDIATE')
            yield db

    def create_product(self, product_id, name, stock=None, source='Cadastro manual'):
        product_id, name = identifier(product_id), text(name, 'Nome', 160)
        stock = None if stock in (None, '') else integer(stock)
        p = provenance('user', source)
        with self.connection() as db:
            if db.execute('SELECT 1 FROM products WHERE id=?', (product_id,)).fetchone():
                raise ValueError('Produto já cadastrado. Use outro identificador.')
            db.execute('INSERT INTO products VALUES (?, ?, ?, ?)', (product_id, name, stock, p))
            if stock is not None:
                db.execute('INSERT INTO stock_history(product_id, quantity, provenance) VALUES (?, ?, ?)', (product_id, stock, p))
        return product_id

    def set_stock(self, product_id, quantity, source):
        quantity, p = integer(quantity), provenance('user', source)
        with self.connection() as db:
            self._product(db, product_id)
            db.execute('UPDATE products SET stock=? WHERE id=?', (quantity, product_id))
            db.execute('INSERT INTO stock_history(product_id, quantity, provenance) VALUES (?, ?, ?)', (product_id, quantity, p))

    @staticmethod
    def _product(db, product_id):
        if not db.execute('SELECT 1 FROM products WHERE id=?', (product_id,)).fetchone():
            raise ValueError('Produto não encontrado.')

    def list_products(self):
        with self.connection() as db:
            return [dict(r) for r in db.execute('SELECT * FROM products ORDER BY name ASC')]

    def product(self, product_id):
        with self.connection() as db:
            row = db.execute('SELECT * FROM products WHERE id=?', (product_id,)).fetchone()
            if not row:
                return None
            res = dict(row)
            official = self._official(db, 'product', product_id)
            res['attributes'] = json.loads(official['content']) if official else {}
            return res

    def import_sales(self, content, source):
        p = provenance('csv', source)
        if not isinstance(content, str) or len(content) > 2_000_000:
            raise ValueError('CSV inválido ou muito grande.')
        digest = hashlib.sha256(content.encode()).hexdigest()
        reader = csv.DictReader(io.StringIO(content.lstrip('\ufeff')), strict=True)
        if reader.fieldnames != ['product_id', 'date', 'quantity', 'revenue']:
            raise ValueError('Cabeçalho esperado: product_id,date,quantity,revenue')
        rows = []
        try:
            for row in reader:
                if None in row or any(v is None for v in row.values()):
                    raise ValueError('CSV com colunas faltantes ou extras.')
                product_id = identifier(row['product_id'])
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', row['date']):
                    raise ValueError('Data esperada: AAAA-MM-DD.')
                sold_on = date.fromisoformat(row['date']).isoformat()
                quantity = integer(row['quantity'])
                revenue = row['revenue'].strip() or None
                if revenue is not None:
                    if not re.fullmatch(r'\d{1,12}(\.\d{1,2})?', revenue) or not Decimal(revenue).is_finite():
                        raise ValueError('Receita deve ser não negativa, com ponto decimal e até duas casas.')
                    revenue = str(Decimal(revenue).quantize(Decimal('0.01')))
                rows.append((digest, product_id, sold_on, quantity, revenue))
        except (csv.Error, InvalidOperation) as exc:
            raise ValueError('CSV inválido.') from exc
        if not rows:
            raise ValueError('CSV sem vendas.')
        with self.connection() as db:
            if db.execute('SELECT 1 FROM sales_imports WHERE digest=?', (digest,)).fetchone():
                raise ValueError('Este CSV já foi importado; nenhuma venda foi duplicada.')
            for row in rows:
                self._product(db, row[1])
            db.execute('INSERT INTO sales_imports VALUES (?, ?)', (digest, p))
            db.executemany('INSERT INTO sales(import_digest,product_id,sold_on,quantity,revenue) VALUES (?, ?, ?, ?, ?)', rows)
        return len(rows)

    @staticmethod
    def _official(db, kind, owner):
        return db.execute('SELECT * FROM bible_versions WHERE kind=? AND owner=? AND approved_at IS NOT NULL ORDER BY version DESC LIMIT 1', (kind, owner)).fetchone()

    @staticmethod
    def _validate_content(kind, content):
        if kind not in ('brand', 'product') or not isinstance(content, dict) or not content:
            raise ValueError('Ficha inválida ou vazia.')
        if not set(content) <= set(BRAND_FIELDS if kind == 'brand' else PRODUCT_FIELDS):
            raise ValueError('Atributo desconhecido.')
        if kind == 'brand':
            return {k: text(v, k) for k, v in content.items()}
        result = {}
        for k, v in content.items():
            if not isinstance(v, dict) or set(v) != {'value', 'protection'} or v['protection'] not in ('free', 'protected', 'critical'):
                raise ValueError('Cada atributo precisa de valor e proteção free/protected/critical.')
            result[k] = {'value': text(v['value'], k), 'protection': v['protection']}
        return result

    def propose(self, kind, owner, content, source, source_kind='user'):
        content = self._validate_content(kind, content)
        p = provenance(source_kind, source)
        if kind == 'brand' and owner != 'global':
            raise ValueError('A marca oficial usa o escopo global.')
        with self.connection() as db:
            if kind == 'product':
                self._product(db, owner)
            official = self._official(db, kind, owner)
            version = db.execute('SELECT COALESCE(MAX(version),0)+1 FROM bible_versions WHERE kind=? AND owner=?', (kind, owner)).fetchone()[0]
            return db.execute('INSERT INTO bible_versions(kind,owner,version,base_id,content,provenance) VALUES (?,?,?,?,?,?)',
                              (kind, owner, version, official['id'] if official else None, json.dumps(content, ensure_ascii=False), p)).lastrowid

    def approve(self, version_id, approver, confirm_protected=False):
        approver = text(approver, 'Responsável', 160)
        with self.connection() as db:
            row = db.execute('SELECT * FROM bible_versions WHERE id=?', (integer(version_id),)).fetchone()
            if not row or row['approved_at']:
                raise ValueError('Proposta inexistente ou já aprovada.')
            official = self._official(db, row['kind'], row['owner'])
            if (official['id'] if official else None) != row['base_id']:
                raise ValueError('A versão oficial mudou. Crie uma proposta a partir da versão atual.')
            if official and row['kind'] == 'product':
                old, new = json.loads(official['content']), json.loads(row['content'])
                for key, previous in old.items():
                    if previous == new.get(key):
                        continue
                    if previous['protection'] == 'critical':
                        raise ValueError(f'{key}: atributo critical não pode ser alterado nem removido.')
                    if previous['protection'] == 'protected' and confirm_protected is not True:
                        raise ValueError(f'{key}: confirme explicitamente a alteração protected.')
            db.execute('UPDATE bible_versions SET approved_by=?, approved_at=? WHERE id=?',
                       (approver, datetime.now(timezone.utc).isoformat(), row['id']))

    def override_brand(self, campaign, content, source):
        campaign = identifier(campaign)
        content = self._validate_content('brand', content)
        p = provenance('user', source)
        with self.connection() as db:
            official = self._official(db, 'brand', 'global')
            if not official:
                raise ValueError('Aprove uma Brand Bible global primeiro.')
            db.execute('INSERT INTO campaign_overrides VALUES (?, ?, ?, ?) ON CONFLICT(campaign) DO UPDATE SET brand_version=excluded.brand_version,content=excluded.content,provenance=excluded.provenance',
                       (campaign, official['id'], json.dumps(content, ensure_ascii=False), p))

    def brand_for(self, campaign=None):
        with self.connection() as db:
            override = db.execute('SELECT * FROM campaign_overrides WHERE campaign=?', (campaign,)).fetchone() if campaign else None
            base = db.execute('SELECT * FROM bible_versions WHERE id=?', (override['brand_version'],)).fetchone() if override else self._official(db, 'brand', 'global')
            result = json.loads(base['content']) if base else {}
            if override:
                result.update(json.loads(override['content']))
            return result

    def product_bible_for(self, product_id):
        with self.connection() as db:
            row = self._official(db, 'product', product_id)
            return json.loads(row['content']) if row else {}


    def add_reference(self, photo, *, product_id=None, scope='permanent', campaign=None,
                      origin='unknown', source_reference='', rights='unknown', angle='front', quality=0):
        if not isinstance(photo, bytes) or not 16 <= len(photo) <= 5_000_000:
            raise ValueError('Envie uma imagem PNG ou JPEG de até 5 MB.')
        if photo.startswith(b'\x89PNG\r\n\x1a\n') and photo[12:16] == b'IHDR':
            mime, ext = 'image/png', 'png'
        elif photo.startswith(b'\xff\xd8\xff') and photo.endswith(b'\xff\xd9'):
            mime, ext = 'image/jpeg', 'jpg'
        else:
            raise ValueError('Formato de imagem não permitido. Use PNG ou JPEG.')
        if scope not in ('permanent', 'campaign') or (scope == 'campaign') != bool(campaign):
            raise ValueError('Referência de campanha exige identificador; permanente não recebe campanha.')
        if campaign:
            identifier(campaign)
        if origin not in ('own', 'licensed', 'public_domain', 'external', 'unknown') or rights not in ('confirmed', 'unknown') or angle not in ANGLES:
            raise ValueError('Origem, direitos ou ângulo inválidos.')
        source_reference = text(source_reference, 'Origem da referência')
        quality = integer(quality)
        if quality > 5:
            raise ValueError('Qualidade: use 0 a 5.')
        usage = 'inspiration_only' if rights == 'unknown' or origin in ('external', 'unknown') else 'commercial_reference'
        analysis = self.vision.analyze_reference(photo)
        if set(analysis) != {'provider', 'simulated', 'attributes'} or set(analysis['attributes']) != set(VISUAL_FIELDS):
            raise ValueError('Resposta de visão inválida.')
        ref_id = uuid4().hex
        key = f'references/{hashlib.sha256(photo).hexdigest()}.{ext}'
        with self.connection() as db:
            if product_id:
                self._product(db, product_id)
            self.storage.put(key, photo)
            db.execute('INSERT INTO visual_references VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       (ref_id, key, mime, product_id, scope, campaign, origin, source_reference, rights, usage, angle, quality,
                        json.dumps(analysis, ensure_ascii=False), provenance('user', source_reference)))
        return ref_id

    def reference_set(self, product_id, task, campaign=None, manual_ids=None):
        if task not in TASKS:
            raise ValueError('Tarefa desconhecida.')
        with self.connection() as db:
            self._product(db, product_id)
            rows = [dict(r) for r in db.execute("SELECT * FROM visual_references WHERE product_id=? AND (scope='permanent' OR campaign=?)", (product_id, campaign))]
        if manual_ids is not None:
            if not manual_ids or len(manual_ids) != len(set(manual_ids)):
                raise ValueError('Selecione referências distintas.')
            by_id = {r['id']: r for r in rows}
            if any(r not in by_id for r in manual_ids):
                raise ValueError('Referência fora do produto ou da campanha.')
            return [by_id[r] for r in manual_ids]
        preferred = TASKS[task]
        return sorted(rows, key=lambda r: (preferred.index(r['angle']) if r['angle'] in preferred else len(preferred), -r['quality'], r['id']))[:5]

    def analyze_product(self, product_id, campaign=None):
        references = self.reference_set(product_id, 'catalog', campaign)
        if len(references) < 3:
            raise ValueError('Adicione pelo menos 3 fotos. A análise usa até 5 referências.')
        result = self.vision.analyze_product([self.storage.get(r['asset_key']) for r in references])
        if set(result) != {'provider', 'simulated', 'attributes'} or set(result['attributes']) != set(PRODUCT_FIELDS):
            raise ValueError('Resposta de visão inválida.')
        attributes = self._validate_content('product', result['attributes'])
        return self.propose('product', product_id, attributes,
                            json.dumps({'provider': result['provider'], 'simulated': result['simulated'], 'references': [r['id'] for r in references]}), 'automatic_analysis')

    def snapshot(self):
        with self.connection() as db:
            return {name: [dict(row) for row in db.execute('SELECT * FROM ' + name)]
                    for name in ('products', 'stock_history', 'sales', 'sales_imports', 'bible_versions', 'campaign_overrides', 'visual_references')}
