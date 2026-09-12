"""Adaptadores de motores de imagem e provedores customizados.

Todos os adaptadores implementam o contrato ImageEngine e executam chamadas externas
através de ExternalGateway, garantindo que o modo mock recuse egress antes do transporte.
"""
import json
import time
from typing import Any, Callable, Dict, Mapping, Optional
import urllib.request
import urllib.error

from kiros.core.contracts import ImageEngine
from kiros.infrastructure.security import ExternalGateway, Secret
from kiros.providers.catalog import (
    validate_model,
    validate_provider_type,
    get_default_endpoint,
)


class ProviderError(Exception):
    """Erro sanitizado ao comunicar com provider."""
    pass


def _sanitize_error_message(msg: str, secret: Optional[str] = None) -> str:
    """Garante que segredos ou detalhes de autenticação não vazem na mensagem."""
    cleaned = str(msg)
    if secret and secret in cleaned:
        cleaned = cleaned.replace(secret, '[REDACTED]')
    # Sanitização genérica de padrões de chave
    import re
    cleaned = re.sub(r'(Bearer\s+)[A-Za-z0-9_\-\.]{8,}', r'\1[REDACTED]', cleaned)
    cleaned = re.sub(r'(key=)[A-Za-z0-9_\-\.]{8,}', r'\1[REDACTED]', cleaned)
    cleaned = re.sub(r'(api[_-]?key[\'":\s=]+)[A-Za-z0-9_\-\.]{8,}', r'\1[REDACTED]', cleaned, flags=re.IGNORECASE)
    return cleaned


class BaseImageEngine:
    """Base para adaptadores de imagem com controle de latência, sanitização e gateway."""

    def __init__(
        self,
        provider_type: str,
        gateway: ExternalGateway,
        model: str,
        endpoint: Optional[str] = None,
        secret: Optional[str] = None,
        config: Optional[Mapping[str, object]] = None,
        transport: Optional[Callable[[urllib.request.Request, float], Dict[str, Any]]] = None,
    ):
        self.provider_type = validate_provider_type(provider_type)
        self.model = validate_model(self.provider_type, model)
        self.gateway = gateway
        self.endpoint = (endpoint or '').strip() or get_default_endpoint(self.provider_type, self.model)
        self._secret = Secret(secret) if secret else None
        self.config = dict(config or {})
        self._transport = transport

    @property
    def secret_value(self) -> Optional[str]:
        return self._secret.value if self._secret else None

    def _execute_http(self, req: urllib.request.Request, timeout: float = 30.0) -> Dict[str, Any]:
        """Executa transporte com medição de latência e captura segura de erros."""
        if self._transport is not None:
            res = dict(self._transport(req, timeout))
            if 'error' in res:
                res['error'] = _sanitize_error_message(res['error'], self.secret_value)
            return res

        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                latency_ms = int((time.perf_counter() - start) * 1000)
                body = response.read().decode('utf-8')
                data = json.loads(body) if body else {}
                return {'status': response.status, 'data': data, 'latency_ms': latency_ms}
        except urllib.error.HTTPError as err:
            latency_ms = int((time.perf_counter() - start) * 1000)
            err_body = ''
            try:
                err_body = err.read().decode('utf-8')
            except Exception:
                pass
            msg = f"HTTP {err.code}: {err.reason} - {err_body}"
            sanitized = _sanitize_error_message(msg, self.secret_value)
            return {'status': err.code, 'error': sanitized, 'latency_ms': latency_ms}
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            latency_ms = int((time.perf_counter() - start) * 1000)
            msg = f"Erro de conexão/timeout: {type(err).__name__} - {str(err)}"
            sanitized = _sanitize_error_message(msg, self.secret_value)
            return {'status': 503, 'error': sanitized, 'latency_ms': latency_ms}

    def _call_gateway(self, operation: Callable[[], Dict[str, Any]], paid: bool = True, approved: bool = False) -> Dict[str, Any]:
        """Encaminha operação pelo ExternalGateway obrigatório."""
        return self.gateway.call(operation, paid=paid, publish=False, approved=approved)

    def test_connection(self) -> Dict[str, Any]:
        """Testa conectividade e validação da chave/endpoint."""
        raise NotImplementedError

    def test_simple(self) -> Dict[str, Any]:
        """Executa teste simples de geração de imagem."""
        raise NotImplementedError

    def generate(self, brief: Mapping[str, object]) -> str:
        """Gera imagem com base no brief."""
        raise NotImplementedError


class GeminiImageEngine(BaseImageEngine, ImageEngine):
    """Adaptador para Google Gemini / Imagen 3 oficial."""

    def __init__(self, gateway: ExternalGateway, model: str = 'imagen-3.0-generate-002', **kwargs):
        super().__init__('gemini', gateway, model, **kwargs)

    def _build_request(self, prompt: str, aspect_ratio: str = '1:1') -> urllib.request.Request:
        url = f"{self.endpoint}/{self.model}:predict"
        headers = {'Content-Type': 'application/json'}
        if self.secret_value:
            headers['x-goog-api-key'] = self.secret_value
        payload = json.dumps({
            'instances': [{'prompt': prompt}],
            'parameters': {'sampleCount': 1, 'aspectRatio': aspect_ratio},
        }).encode('utf-8')
        return urllib.request.Request(url, data=payload, headers=headers, method='POST')

    def test_connection(self) -> Dict[str, Any]:
        def op():
            req = self._build_request('connection test ping')
            res = self._execute_http(req, timeout=10.0)
            if res.get('status') == 200:
                return {
                    'status': 'ok',
                    'latency_ms': res.get('latency_ms', 0),
                    'message': f"Conexão bem-sucedida com Gemini ({self.model}).",
                }
            return {
                'status': 'error',
                'latency_ms': res.get('latency_ms', 0),
                'message': res.get('error', f"Erro HTTP {res.get('status')}"),
            }
        return self._call_gateway(op, paid=False, approved=True)

    def test_simple(self) -> Dict[str, Any]:
        def op():
            req = self._build_request('Um aroma sutil de lavanda e bergamota sobre mármore claro')
            res = self._execute_http(req, timeout=20.0)
            if res.get('status') == 200:
                return {
                    'status': 'ok',
                    'latency_ms': res.get('latency_ms', 0),
                    'message': 'Geração de teste concluída com sucesso.',
                    'asset_key': 'gemini-test-sample.png',
                }
            return {
                'status': 'error',
                'latency_ms': res.get('latency_ms', 0),
                'message': res.get('error', f"Erro HTTP {res.get('status')}"),
            }
        return self._call_gateway(op, paid=True, approved=True)

    def generate(self, brief: Mapping[str, object]) -> str:
        prompt = str(brief.get('prompt', 'Aroma KIROS Studio'))
        aspect_ratio = str(brief.get('aspect_ratio', '1:1'))

        def op():
            req = self._build_request(prompt, aspect_ratio)
            res = self._execute_http(req, timeout=30.0)
            if res.get('status') == 200:
                return f"gemini:{self.model}:{int(time.time())}"
            raise ProviderError(res.get('error', f"Erro na geração Gemini: HTTP {res.get('status')}"))
        return self._call_gateway(op, paid=True, approved=bool(brief.get('approved', False)))


class OpenAIImageEngine(BaseImageEngine, ImageEngine):
    """Adaptador para OpenAI DALL-E oficial."""

    def __init__(self, gateway: ExternalGateway, model: str = 'dall-e-3', **kwargs):
        super().__init__('openai', gateway, model, **kwargs)

    def _build_request(self, prompt: str, size: str = '1024x1024') -> urllib.request.Request:
        url = self.endpoint
        headers = {'Content-Type': 'application/json'}
        if self.secret_value:
            headers['Authorization'] = f'Bearer {self.secret_value}'
        payload = json.dumps({
            'model': self.model,
            'prompt': prompt,
            'n': 1,
            'size': size,
        }).encode('utf-8')
        return urllib.request.Request(url, data=payload, headers=headers, method='POST')

    def test_connection(self) -> Dict[str, Any]:
        def op():
            # Teste de conexão envia prompt mínimo
            req = self._build_request('connection test ping')
            res = self._execute_http(req, timeout=10.0)
            if res.get('status') == 200:
                return {
                    'status': 'ok',
                    'latency_ms': res.get('latency_ms', 0),
                    'message': f"Conexão bem-sucedida com OpenAI ({self.model}).",
                }
            return {
                'status': 'error',
                'latency_ms': res.get('latency_ms', 0),
                'message': res.get('error', f"Erro HTTP {res.get('status')}"),
            }
        return self._call_gateway(op, paid=False, approved=True)

    def test_simple(self) -> Dict[str, Any]:
        def op():
            req = self._build_request('Vela aromática KIROS em vidro fosco sobre mesa de madeira nobre')
            res = self._execute_http(req, timeout=20.0)
            if res.get('status') == 200:
                return {
                    'status': 'ok',
                    'latency_ms': res.get('latency_ms', 0),
                    'message': 'Geração de teste OpenAI concluída com sucesso.',
                    'asset_key': 'openai-test-sample.png',
                }
            return {
                'status': 'error',
                'latency_ms': res.get('latency_ms', 0),
                'message': res.get('error', f"Erro HTTP {res.get('status')}"),
            }
        return self._call_gateway(op, paid=True, approved=True)

    def generate(self, brief: Mapping[str, object]) -> str:
        prompt = str(brief.get('prompt', 'Aroma KIROS'))
        size = str(brief.get('size', '1024x1024'))

        def op():
            req = self._build_request(prompt, size)
            res = self._execute_http(req, timeout=30.0)
            if res.get('status') == 200:
                return f"openai:{self.model}:{int(time.time())}"
            raise ProviderError(res.get('error', f"Erro na geração OpenAI: HTTP {res.get('status')}"))
        return self._call_gateway(op, paid=True, approved=bool(brief.get('approved', False)))


class FireflyImageEngine(BaseImageEngine, ImageEngine):
    """Adaptador para Adobe Firefly Services oficial."""

    def __init__(self, gateway: ExternalGateway, model: str = 'firefly-image-3', **kwargs):
        super().__init__('firefly', gateway, model, **kwargs)

    def _build_request(self, prompt: str) -> urllib.request.Request:
        url = self.endpoint
        headers = {'Content-Type': 'application/json'}
        if self.secret_value:
            headers['Authorization'] = f'Bearer {self.secret_value}'
        client_id = str(self.config.get('client_id', 'kiros-studio'))
        headers['x-api-key'] = client_id
        payload = json.dumps({
            'prompt': prompt,
            'numVariations': 1,
        }).encode('utf-8')
        return urllib.request.Request(url, data=payload, headers=headers, method='POST')

    def test_connection(self) -> Dict[str, Any]:
        def op():
            req = self._build_request('connection test ping')
            res = self._execute_http(req, timeout=10.0)
            if res.get('status') == 200:
                return {
                    'status': 'ok',
                    'latency_ms': res.get('latency_ms', 0),
                    'message': f"Conexão bem-sucedida com Firefly ({self.model}).",
                }
            return {
                'status': 'error',
                'latency_ms': res.get('latency_ms', 0),
                'message': res.get('error', f"Erro HTTP {res.get('status')}"),
            }
        return self._call_gateway(op, paid=False, approved=True)

    def test_simple(self) -> Dict[str, Any]:
        def op():
            req = self._build_request('Difusor de varetas elegante com luz natural suave')
            res = self._execute_http(req, timeout=20.0)
            if res.get('status') == 200:
                return {
                    'status': 'ok',
                    'latency_ms': res.get('latency_ms', 0),
                    'message': 'Geração de teste Firefly concluída com sucesso.',
                    'asset_key': 'firefly-test-sample.png',
                }
            return {
                'status': 'error',
                'latency_ms': res.get('latency_ms', 0),
                'message': res.get('error', f"Erro HTTP {res.get('status')}"),
            }
        return self._call_gateway(op, paid=True, approved=True)

    def generate(self, brief: Mapping[str, object]) -> str:
        prompt = str(brief.get('prompt', 'Composição de estúdio KIROS'))

        def op():
            req = self._build_request(prompt)
            res = self._execute_http(req, timeout=30.0)
            if res.get('status') == 200:
                return f"firefly:{self.model}:{int(time.time())}"
            raise ProviderError(res.get('error', f"Erro na geração Firefly: HTTP {res.get('status')}"))
        return self._call_gateway(op, paid=True, approved=bool(brief.get('approved', False)))


class CustomImageProvider(BaseImageEngine, ImageEngine):
    """Adaptador para provedores de imagem customizados / auto-hospedados."""

    def __init__(self, gateway: ExternalGateway, model: str, endpoint: str, **kwargs):
        if not endpoint or not endpoint.strip():
            raise ValueError('Endpoint é obrigatório para provedores customizados.')
        super().__init__('custom', gateway, model, endpoint=endpoint, **kwargs)

    def _build_request(self, prompt: str) -> urllib.request.Request:
        headers = {'Content-Type': 'application/json'}
        if self.secret_value:
            auth_header = str(self.config.get('auth_header', 'Authorization'))
            auth_prefix = str(self.config.get('auth_prefix', 'Bearer '))
            headers[auth_header] = f"{auth_prefix}{self.secret_value}".strip()
        payload = json.dumps({
            'model': self.model,
            'prompt': prompt,
            'config': self.config,
        }).encode('utf-8')
        return urllib.request.Request(self.endpoint, data=payload, headers=headers, method='POST')

    def test_connection(self) -> Dict[str, Any]:
        def op():
            req = self._build_request('connection test ping')
            res = self._execute_http(req, timeout=10.0)
            if res.get('status') == 200:
                return {
                    'status': 'ok',
                    'latency_ms': res.get('latency_ms', 0),
                    'message': f"Conexão bem-sucedida com provedor customizado ({self.model}).",
                }
            return {
                'status': 'error',
                'latency_ms': res.get('latency_ms', 0),
                'message': res.get('error', f"Erro HTTP {res.get('status')}"),
            }
        return self._call_gateway(op, paid=False, approved=True)

    def test_simple(self) -> Dict[str, Any]:
        def op():
            req = self._build_request('Teste simples de imagem customizada')
            res = self._execute_http(req, timeout=20.0)
            if res.get('status') == 200:
                return {
                    'status': 'ok',
                    'latency_ms': res.get('latency_ms', 0),
                    'message': 'Geração de teste customizado concluída com sucesso.',
                    'asset_key': 'custom-test-sample.png',
                }
            return {
                'status': 'error',
                'latency_ms': res.get('latency_ms', 0),
                'message': res.get('error', f"Erro HTTP {res.get('status')}"),
            }
        return self._call_gateway(op, paid=True, approved=True)

    def generate(self, brief: Mapping[str, object]) -> str:
        prompt = str(brief.get('prompt', ''))

        def op():
            req = self._build_request(prompt)
            res = self._execute_http(req, timeout=30.0)
            if res.get('status') == 200:
                return f"custom:{self.model}:{int(time.time())}"
            raise ProviderError(res.get('error', f"Erro no provedor customizado: HTTP {res.get('status')}"))
        return self._call_gateway(op, paid=True, approved=bool(brief.get('approved', False)))
