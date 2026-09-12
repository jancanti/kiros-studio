"""Image Engine Router: roteamento por campanha, slide e recomendação automática."""
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from kiros.core.contracts import Provenance
from kiros.infrastructure.local import SQLiteDatabase
from kiros.providers.catalog import get_model_cost, validate_model, validate_provider_type
from kiros.providers.manager import ProviderManager


class ImageEngineRouter:
    """Roteador de motores de imagem por campanha, slide ou recomendação automática."""

    def __init__(self, db: SQLiteDatabase, provider_manager: Optional[ProviderManager] = None):
        self.db = db
        self.provider_manager = provider_manager

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def set_campaign_default(
        self,
        campaign_id: str,
        engine: str,
        model: str,
        provenance: Provenance,
    ) -> None:
        cid = (campaign_id or '').strip()
        if not cid:
            raise ValueError('ID da campanha é obrigatório.')
        p_type = validate_provider_type(engine)
        p_model = validate_model(p_type, model)

        current = self.get_campaign_routing(cid)
        slide_overrides = current['slide_overrides'] if current else {}
        now = self._now()

        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''INSERT INTO campaign_engine_routing (campaign_id, default_engine, default_model, slide_overrides_json, provenance, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(campaign_id) DO UPDATE SET
                       default_engine=excluded.default_engine,
                       default_model=excluded.default_model,
                       provenance=excluded.provenance,
                       updated_at=excluded.updated_at''',
                (cid, p_type, p_model, json.dumps(slide_overrides), provenance.source, now),
            )

    def set_slide_override(
        self,
        campaign_id: str,
        slide_index: int,
        engine: str,
        model: str,
        provenance: Provenance,
    ) -> None:
        cid = (campaign_id or '').strip()
        if not cid:
            raise ValueError('ID da campanha é obrigatório.')
        if slide_index < 0:
            raise ValueError('Índice do slide deve ser não negativo.')
        p_type = validate_provider_type(engine)
        p_model = validate_model(p_type, model)

        current = self.get_campaign_routing(cid)
        if not current:
            # Se não houver configuração padrão, inicializa com a recomendação automática como padrão
            rec = self.recommend()
            default_engine = rec['provider']
            default_model = rec['model']
            slide_overrides = {}
        else:
            default_engine = current['default_engine']
            default_model = current['default_model']
            slide_overrides = current['slide_overrides']

        slide_overrides[str(slide_index)] = {
            'engine': p_type,
            'model': p_model,
            'provenance': provenance.source,
            'set_at': self._now(),
        }

        now = self._now()
        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''INSERT INTO campaign_engine_routing (campaign_id, default_engine, default_model, slide_overrides_json, provenance, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(campaign_id) DO UPDATE SET
                       slide_overrides_json=excluded.slide_overrides_json,
                       provenance=excluded.provenance,
                       updated_at=excluded.updated_at''',
                (cid, default_engine, default_model, json.dumps(slide_overrides), provenance.source, now),
            )

    def clear_slide_override(self, campaign_id: str, slide_index: int) -> None:
        current = self.get_campaign_routing(campaign_id)
        if not current or str(slide_index) not in current['slide_overrides']:
            return
        overrides = current['slide_overrides']
        del overrides[str(slide_index)]
        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                'UPDATE campaign_engine_routing SET slide_overrides_json=?, updated_at=? WHERE campaign_id=?',
                (json.dumps(overrides), self._now(), campaign_id),
            )

    def get_campaign_routing(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM campaign_engine_routing WHERE campaign_id=?', (campaign_id,)).fetchone()
            if not row:
                return None
            res = dict(row)
            res['slide_overrides'] = json.loads(res.get('slide_overrides_json', '{}'))
            return res

    def recommend(self, slide_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Gera recomendação automática com provider, modelo, motivo, custo estimado, confiança e alternativas."""
        ctx = slide_context or {}
        task_type = str(ctx.get('type', 'ambient')).lower()
        budget_priority = str(ctx.get('budget_priority', 'balanced')).lower()

        if budget_priority == 'low' or budget_priority == 'economy':
            provider = 'gemini'
            model = 'imagen-3.0-fast-generate-001'
            reason = 'Otimizado para economia de orçamento e iteração rápida com boa qualidade base.'
            confidence = 0.86
            alternatives = [
                {
                    'provider': 'openai',
                    'model': 'dall-e-2',
                    'estimated_cost': get_model_cost('openai', 'dall-e-2'),
                    'confidence': 0.78,
                    'reason': 'Custo reduzido para rascunhos simples.',
                },
                {
                    'provider': 'gemini',
                    'model': 'imagen-3.0-generate-002',
                    'estimated_cost': get_model_cost('gemini', 'imagen-3.0-generate-002'),
                    'confidence': 0.94,
                    'reason': 'Maior refinamento fotográfico por pequena diferença de custo.',
                },
            ]
        elif task_type in ('conceptual', 'storytelling', 'lifestyle_narrative'):
            provider = 'openai'
            model = 'dall-e-3'
            reason = 'Interpretação semântica sofisticada para cenas conceituais e metáforas visuais da marca.'
            confidence = 0.91
            alternatives = [
                {
                    'provider': 'gemini',
                    'model': 'imagen-3.0-generate-002',
                    'estimated_cost': get_model_cost('gemini', 'imagen-3.0-generate-002'),
                    'confidence': 0.85,
                    'reason': 'Renderização fotográfica com custo ligeiramente inferior.',
                },
                {
                    'provider': 'firefly',
                    'model': 'firefly-image-3',
                    'estimated_cost': get_model_cost('firefly', 'firefly-image-3'),
                    'confidence': 0.80,
                    'reason': 'Composição editorial e segurança comercial.',
                },
            ]
        elif task_type in ('studio', 'packshot', 'catalog'):
            provider = 'firefly'
            model = 'firefly-image-3'
            reason = 'Excelente para composição de estúdio, iluminação controlada e isolamento de produto.'
            confidence = 0.89
            alternatives = [
                {
                    'provider': 'gemini',
                    'model': 'imagen-3.0-generate-002',
                    'estimated_cost': get_model_cost('gemini', 'imagen-3.0-generate-002'),
                    'confidence': 0.87,
                    'reason': 'Excelente fidelidade de texturas (vidro e cera).',
                },
                {
                    'provider': 'openai',
                    'model': 'dall-e-3',
                    'estimated_cost': get_model_cost('openai', 'dall-e-3'),
                    'confidence': 0.80,
                    'reason': 'Variações conceituais alternativas.',
                },
            ]
        else:
            # 'ambient', 'texture', 'product_closeup' e padrão
            provider = 'gemini'
            model = 'imagen-3.0-generate-002'
            reason = 'Excelente fidelidade em texturas de cera e vidro, iluminação realista e menor custo por imagem.'
            confidence = 0.93
            alternatives = [
                {
                    'provider': 'firefly',
                    'model': 'firefly-image-3',
                    'estimated_cost': get_model_cost('firefly', 'firefly-image-3'),
                    'confidence': 0.86,
                    'reason': 'Composição refinada de estúdio para catálogo de luxo.',
                },
                {
                    'provider': 'openai',
                    'model': 'dall-e-3',
                    'estimated_cost': get_model_cost('openai', 'dall-e-3'),
                    'confidence': 0.82,
                    'reason': 'Boa compreensão de composição e ambiência quente.',
                },
            ]

        cost = get_model_cost(provider, model) or 0.030

        return {
            'provider': provider,
            'model': model,
            'reason': reason,
            'estimated_cost': cost,
            'confidence': confidence,
            'alternatives': alternatives,
        }

    def resolve(
        self,
        campaign_id: str,
        slide_index: Optional[int] = None,
        slide_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Resolve o motor final: manual prevalece (slide > campanha > recomendação)."""
        routing = self.get_campaign_routing(campaign_id) if campaign_id else None

        # 1. Prioridade máxima: override manual do slide
        if routing and slide_index is not None:
            key = str(slide_index)
            if key in routing.get('slide_overrides', {}):
                ov = routing['slide_overrides'][key]
                cost = get_model_cost(ov['engine'], ov['model']) or 0.0
                return {
                    'provider': ov['engine'],
                    'model': ov['model'],
                    'source': 'slide_override',
                    'is_manual': True,
                    'estimated_cost': cost,
                    'reason': f"Definição manual para o slide {slide_index}.",
                }

        # 2. Prioridade secundária: default da campanha
        if routing and routing.get('default_engine') and routing.get('default_model'):
            cost = get_model_cost(routing['default_engine'], routing['default_model']) or 0.0
            return {
                'provider': routing['default_engine'],
                'model': routing['default_model'],
                'source': 'campaign_default',
                'is_manual': True,
                'estimated_cost': cost,
                'reason': 'Padrão configurado manualmente para a campanha.',
            }

        # 3. Recomendação automática com Fallback de Provedor Ativo
        rec = self.recommend(slide_context)
        rec['source'] = 'automatic_recommendation'
        rec['is_manual'] = False

        # Fallback de crédito/disponibilidade: Se o provedor recomendado não estiver ativo no Manager, faz fallback
        if self.provider_manager:
            active_providers = [p for p in self.provider_manager.list_providers() if p.get('is_active')]
            if active_providers:
                active_types = {p['type'] for p in active_providers}
                if rec['provider'] not in active_types:
                    # Escolhe o primeiro ativo das alternativas ou o primeiro provedor ativo
                    fallback_prov = active_providers[0]
                    rec['original_provider'] = rec['provider']
                    rec['provider'] = fallback_prov['type']
                    rec['model'] = fallback_prov['model']
                    rec['fallback_used'] = True
                    rec['reason'] += f" (Fallback automático ativado: '{rec['original_provider']}' indisponível ou sem créditos, redirecionado para '{fallback_prov['name']}')."

        return rec


