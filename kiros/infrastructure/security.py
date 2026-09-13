"""Toda operação externa do produto deve passar por ExternalGateway."""
import os
from dataclasses import dataclass, field
from typing import Callable, TypeVar

T = TypeVar('T')


@dataclass(frozen=True)
class Policy:
    mode: str = 'mock'
    allow_paid: bool = False
    allow_publish: bool = False

    def __post_init__(self):
        if self.mode not in ('mock', 'live'):
            raise ValueError('KIROS_PROVIDER_MODE inválido')

    @classmethod
    def from_env(cls):
        return cls(os.getenv('KIROS_PROVIDER_MODE', 'mock'),
                   os.getenv('KIROS_ALLOW_PAID_APIS', '0') == '1',
                   os.getenv('KIROS_ALLOW_PUBLISH', '0') == '1')


@dataclass(frozen=True)
class Secret:
    value: str = field(repr=False)

    def __str__(self):
        return '[REDACTED]'


class ExternalGateway:
    def __init__(self, policy: Policy):
        self.policy = policy

    def set_policy(self, mode: str, allow_paid: bool = False, allow_publish: bool = False):
        self.policy = Policy(mode=mode, allow_paid=allow_paid, allow_publish=allow_publish)

    def call(self, operation: Callable[[], T], *, paid=True, publish=False,
             approved=False) -> T:
        if self.policy.mode == 'mock':
            raise PermissionError('Chamadas externas bloqueadas no modo mock')
        if (paid or publish) and not approved:
            raise PermissionError('Aprovação específica necessária')
        if paid and not self.policy.allow_paid:
            raise PermissionError('APIs pagas bloqueadas')
        if publish and not self.policy.allow_publish:
            raise PermissionError('Publicação bloqueada')
        # Mensagem do provider pode conter chave, URL assinada ou prompt privado.
        try:
            return operation()
        except Exception:
            raise RuntimeError('Falha na operação externa; detalhes privados omitidos') from None
