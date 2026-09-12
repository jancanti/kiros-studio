"""Catálogo oficial de modelos, endpoints e tabelas de preço para provedores de imagem.

IDs de modelo verificados contra a documentação oficial vigente em 2026-09-12:
- Google Gemini (Imagen 3): https://ai.google.dev/gemini-api/docs/imagen
- OpenAI (DALL-E): https://platform.openai.com/docs/api-reference/images/create
- Adobe Firefly Services: https://developer.adobe.com/firefly-api/docs/guides/api/image_generation/
"""
from typing import Mapping, Optional, Sequence


OFFICIAL_CATALOG = {
    'gemini': {
        'name': 'Google Gemini (Imagen 3)',
        'docs_url': 'https://ai.google.dev/gemini-api/docs/imagen',
        'checked_date': '2026-09-12',
        'default_endpoint': 'https://generativelanguage.googleapis.com/v1beta/models',
        'models': {
            'imagen-3.0-generate-002': {
                'name': 'Imagen 3 (Qualidade padrão)',
                'cost': 0.030,
                'aspect_ratios': ['1:1', '3:4', '4:3', '9:16', '16:9'],
                'strengths': 'Excelente em texturas, materiais fotográficos e iluminação realista.',
            },
            'imagen-3.0-fast-generate-001': {
                'name': 'Imagen 3 Fast',
                'cost': 0.020,
                'aspect_ratios': ['1:1', '3:4', '4:3', '9:16', '16:9'],
                'strengths': 'Baixa latência para rascunhos rápidos e prototipagem.',
            },
        },
    },
    'openai': {
        'name': 'OpenAI (DALL-E)',
        'docs_url': 'https://platform.openai.com/docs/api-reference/images/create',
        'checked_date': '2026-09-12',
        'default_endpoint': 'https://api.openai.com/v1/images/generations',
        'models': {
            'dall-e-3': {
                'name': 'DALL-E 3',
                'cost': 0.040,
                'aspect_ratios': ['1024x1024', '1024x1792', '1792x1024'],
                'strengths': 'Interpretação semântica sofisticada e cenas conceituais complexas.',
            },
            'dall-e-2': {
                'name': 'DALL-E 2',
                'cost': 0.020,
                'aspect_ratios': ['256x256', '512x512', '1024x1024'],
                'strengths': 'Gerações simples de menor custo.',
            },
        },
    },
    'firefly': {
        'name': 'Adobe Firefly Services',
        'docs_url': 'https://developer.adobe.com/firefly-api/docs/guides/api/image_generation/',
        'checked_date': '2026-09-12',
        'default_endpoint': 'https://firefly-api.adobe.io/v3/images/generate',
        'models': {
            'firefly-image-3': {
                'name': 'Firefly Image 3',
                'cost': 0.040,
                'aspect_ratios': ['1:1', '4:3', '3:4', '16:9', '9:16'],
                'strengths': 'Design comercial seguro e composição de elementos de estúdio.',
            },
            'firefly-image-2': {
                'name': 'Firefly Image 2',
                'cost': 0.040,
                'aspect_ratios': ['1:1', '4:3', '3:4', '16:9'],
                'strengths': 'Renderização de produto e iluminação controlada.',
            },
        },
    },
}

SUPPORTED_PROVIDER_TYPES = ('gemini', 'openai', 'firefly', 'custom')


def validate_provider_type(provider_type: str) -> str:
    cleaned = (provider_type or '').strip().lower()
    if cleaned not in SUPPORTED_PROVIDER_TYPES:
        raise ValueError(f"Tipo de provedor inválido: '{provider_type}'. Suportados: {', '.join(SUPPORTED_PROVIDER_TYPES)}")
    return cleaned


def validate_model(provider_type: str, model_id: str) -> str:
    p_type = validate_provider_type(provider_type)
    cleaned_model = (model_id or '').strip()
    if not cleaned_model:
        raise ValueError('ID do modelo não pode ser vazio.')
    if p_type in OFFICIAL_CATALOG:
        valid_models = OFFICIAL_CATALOG[p_type]['models']
        if cleaned_model not in valid_models:
            valid_list = ', '.join(sorted(valid_models.keys()))
            raise ValueError(
                f"Modelo '{cleaned_model}' não é válido para {p_type}. "
                f"IDs oficiais suportados: {valid_list}. Não utilize IDs presumidos."
            )
    return cleaned_model


def get_default_endpoint(provider_type: str, model_id: str = '') -> str:
    p_type = validate_provider_type(provider_type)
    if p_type in OFFICIAL_CATALOG:
        return OFFICIAL_CATALOG[p_type]['default_endpoint']
    return ''


def get_model_cost(provider_type: str, model_id: str, custom_config: Optional[Mapping[str, object]] = None) -> Optional[float]:
    p_type = validate_provider_type(provider_type)
    if p_type in OFFICIAL_CATALOG:
        models = OFFICIAL_CATALOG[p_type]['models']
        if model_id in models:
            return float(models[model_id]['cost'])
        return None
    if p_type == 'custom':
        if custom_config and 'cost_per_generation' in custom_config:
            try:
                cost = float(custom_config['cost_per_generation'])
                return cost if cost >= 0 else None
            except (ValueError, TypeError):
                return None
    return None

