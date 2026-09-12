"""Portas do domínio. Nenhuma implementação ou SDK externo neste módulo."""
from typing import Protocol, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Provenance:
    source: str
    reference: str
    recorded_at: str

    def __post_init__(self):
        allowed = {'user', 'brand_bible', 'product_bible', 'campaign', 'csv',
                   'instagram', 'benchmark', 'provider', 'model', 'automatic_analysis'}
        if self.source not in allowed or not self.reference.strip():
            raise ValueError('Origem e referência obrigatórias')
        if datetime.fromisoformat(self.recorded_at).tzinfo is None:
            raise ValueError('Data deve incluir timezone')


class LLMProvider(Protocol):
    def complete(self, prompt: str) -> str: ...


class ImageEngine(Protocol):
    def generate(self, brief: Mapping[str, object]) -> str: ...


class ImagePipelineEngine(Protocol):
    def run(self, stages: Sequence[Mapping[str, object]]) -> Sequence[str]: ...


class StorageProvider(Protocol):
    def put(self, key: str, content: bytes) -> str: ...
    def get(self, key: str) -> bytes: ...


class DatabaseProvider(Protocol):
    def set_preference(self, key: str, value: str, provenance: Provenance) -> None: ...
    def get_preference(self, key: str) -> str: ...


class SocialPublisher(Protocol):
    def publish(self, asset_id: str, caption: str) -> str: ...


class ProductDataProvider(Protocol):
    def products(self) -> Sequence[Mapping[str, object]]: ...


class InventoryProvider(Protocol):
    def inventory(self) -> Sequence[Mapping[str, object]]: ...


class SalesProvider(Protocol):
    def sales(self) -> Sequence[Mapping[str, object]]: ...


class AnalyticsProvider(Protocol):
    def snapshot(self) -> Mapping[str, object]: ...


class VisionProvider(Protocol):
    def analyze_product(self, photos: Sequence[bytes]) -> Mapping[str, object]: ...
    def analyze_reference(self, photo: bytes) -> Mapping[str, object]: ...
