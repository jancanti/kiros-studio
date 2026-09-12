"""Gerenciamento seguro de provedores de imagem e histórico de testes."""
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from kiros.infrastructure.local import SQLiteDatabase
from kiros.infrastructure.security import ExternalGateway
from kiros.providers.catalog import (
    validate_model,
    validate_provider_type,
    get_default_endpoint,
)
from kiros.providers.engines import (
    GeminiImageEngine,
    OpenAIImageEngine,
    FireflyImageEngine,
    CustomImageProvider,
    BaseImageEngine,
)


class ProviderManager:
    """Gerenciador central de configurações, chaves seguras e testes de provedores."""

    def __init__(self, db: SQLiteDatabase, gateway: ExternalGateway):
        self.db = db
        self.gateway = gateway

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def add_provider(
        self,
        provider_id: str,
        provider_type: str,
        name: str,
        model: str,
        endpoint: Optional[str] = None,
        secret: Optional[str] = None,
        is_active: bool = True,
        config: Optional[Dict[str, Any]] = None,
    ) -> str:
        pid = (provider_id or '').strip()
        if not pid or not (1 <= len(pid) <= 64):
            raise ValueError('ID do provedor deve ter entre 1 e 64 caracteres.')
        p_type = validate_provider_type(provider_type)
        p_model = validate_model(p_type, model)
        p_name = (name or '').strip()
        if not p_name:
            p_name = f"{p_type.capitalize()} ({p_model})"
        p_endpoint = (endpoint or '').strip() or get_default_endpoint(p_type, p_model)
        if p_type == 'custom' and not p_endpoint:
            raise ValueError('Endpoint é obrigatório para provedor customizado.')

        now = self._now()
        config_json = json.dumps(config or {}, ensure_ascii=False)
        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''INSERT INTO providers (id, type, name, model, endpoint, secret, is_active, config_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (pid, p_type, p_name, p_model, p_endpoint, secret, 1 if is_active else 0, config_json, now, now),
            )
        return pid

    def update_provider(
        self,
        provider_id: str,
        name: Optional[str] = None,
        model: Optional[str] = None,
        endpoint: Optional[str] = None,
        secret: Optional[str] = None,
        is_active: Optional[bool] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        current = self.get_provider(provider_id, include_secret=True)
        if not current:
            raise ValueError(f"Provedor '{provider_id}' não encontrado.")

        p_type = current['type']
        new_name = (name.strip() if name is not None else current['name'])
        new_model = validate_model(p_type, model) if model is not None else current['model']
        new_endpoint = (endpoint.strip() if endpoint is not None else current['endpoint']) or get_default_endpoint(p_type, new_model)
        new_secret = secret if (secret is not None and secret != '') else current.get('secret')
        new_active = (1 if is_active else 0) if is_active is not None else (1 if current['is_active'] else 0)
        new_config_json = json.dumps(config, ensure_ascii=False) if config is not None else current['config_json']

        now = self._now()
        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''UPDATE providers
                   SET name=?, model=?, endpoint=?, secret=?, is_active=?, config_json=?, updated_at=?
                   WHERE id=?''',
                (new_name, new_model, new_endpoint, new_secret, new_active, new_config_json, now, provider_id),
            )

    def toggle_provider(self, provider_id: str, is_active: bool) -> None:
        with sqlite3.connect(self.db.path) as conn:
            cur = conn.execute('UPDATE providers SET is_active=?, updated_at=? WHERE id=?',
                               (1 if is_active else 0, self._now(), provider_id))
            if cur.rowcount == 0:
                raise ValueError(f"Provedor '{provider_id}' não encontrado.")

    def delete_provider(self, provider_id: str) -> None:
        with sqlite3.connect(self.db.path) as conn:
            conn.execute('DELETE FROM provider_test_logs WHERE provider_id=?', (provider_id,))
            cur = conn.execute('DELETE FROM providers WHERE id=?', (provider_id,))
            if cur.rowcount == 0:
                raise ValueError(f"Provedor '{provider_id}' não encontrado.")

    def get_provider(self, provider_id: str, include_secret: bool = False) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM providers WHERE id=?', (provider_id,)).fetchone()
            if not row:
                return None
            res = dict(row)
            res['is_active'] = bool(res['is_active'])
            raw_secret = res.pop('secret', None)
            res['has_secret'] = bool(raw_secret)
            if include_secret:
                res['secret'] = raw_secret
            else:
                res['secret_preview'] = '••••••••' if raw_secret else 'Não configurado'
            return res

    def list_providers(self, include_secret: bool = False, active_only: bool = False) -> List[Dict[str, Any]]:
        query = 'SELECT * FROM providers'
        params: tuple = ()
        if active_only:
            query += ' WHERE is_active = 1'
        query += ' ORDER BY created_at ASC'
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item['is_active'] = bool(item['is_active'])
                raw_secret = item.pop('secret', None)
                item['has_secret'] = bool(raw_secret)
                if include_secret:
                    item['secret'] = raw_secret
                else:
                    item['secret_preview'] = '••••••••' if raw_secret else 'Não configurado'
                result.append(item)
            return result

    def create_engine(self, provider_id: str, transport: Optional[Any] = None) -> BaseImageEngine:
        prov = self.get_provider(provider_id, include_secret=True)
        if not prov:
            raise ValueError(f"Provedor '{provider_id}' não encontrado.")
        p_type = prov['type']
        model = prov['model']
        endpoint = prov['endpoint']
        secret = prov.get('secret')
        config = json.loads(prov.get('config_json', '{}'))

        kwargs = dict(
            endpoint=endpoint,
            secret=secret,
            config=config,
            transport=transport,
        )

        if p_type == 'gemini':
            return GeminiImageEngine(self.gateway, model=model, **kwargs)
        elif p_type == 'openai':
            return OpenAIImageEngine(self.gateway, model=model, **kwargs)
        elif p_type == 'firefly':
            return FireflyImageEngine(self.gateway, model=model, **kwargs)
        elif p_type == 'custom':
            return CustomImageProvider(self.gateway, model=model, **kwargs)
        raise ValueError(f"Tipo de provedor não suportado: {p_type}")

    def test_connection(self, provider_id: str, transport: Optional[Any] = None) -> Dict[str, Any]:
        engine = self.create_engine(provider_id, transport=transport)
        try:
            result = engine.test_connection()
        except PermissionError as err:
            result = {'status': 'error', 'latency_ms': 0, 'message': str(err)}
        except Exception as err:
            result = {'status': 'error', 'latency_ms': 0, 'message': f"Falha na conexão: {str(err)}"}

        self._record_test_log(provider_id, 'connection', result)
        return result

    def test_simple(self, provider_id: str, transport: Optional[Any] = None) -> Dict[str, Any]:
        engine = self.create_engine(provider_id, transport=transport)
        try:
            result = engine.test_simple()
        except PermissionError as err:
            result = {'status': 'error', 'latency_ms': 0, 'message': str(err)}
        except Exception as err:
            result = {'status': 'error', 'latency_ms': 0, 'message': f"Falha no teste: {str(err)}"}

        self._record_test_log(provider_id, 'simple_generation', result)
        return result

    def _record_test_log(self, provider_id: str, test_type: str, result: Dict[str, Any]) -> None:
        now = self._now()
        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''INSERT INTO provider_test_logs (provider_id, test_type, status, latency_ms, message, executed_at)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (
                    provider_id,
                    test_type,
                    result.get('status', 'error'),
                    int(result.get('latency_ms', 0)),
                    str(result.get('message', '')),
                    now,
                ),
            )

    def get_test_logs(self, provider_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        query = 'SELECT * FROM provider_test_logs'
        params: list = []
        if provider_id:
            query += ' WHERE provider_id = ?'
            params.append(provider_id)
        query += ' ORDER BY id DESC LIMIT ?'
        params.append(limit)

        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(r) for r in rows]

