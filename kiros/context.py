"""Economia de tokens, regra de contexto seletivo, orçamento, cache e deduplicação.

Princípio: não triturar tokens antes da aprovação de ações relevantes (Seções 25 e 77).
Antes de qualquer chamada:
1. determinar informação necessária;
2. recuperar somente essa informação;
3. compactar;
4. eliminar redundância;
5. executar.
"""
import hashlib
import json
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set

from kiros.cost import CostManager, UnknownPricingError


class ContextBudgetExceededError(ValueError):
    """Lançado quando o contexto excede o orçamento sem possibilidade de compressão."""
    pass


class ContextOptimizer:
    """Otimizador de contexto: seleção cirúrgica de dados da marca/produto, cache e orçamento."""

    def __init__(self, cost_manager: Optional[CostManager] = None):
        self.cost_manager = cost_manager
        # Cache em memória indexado por hash determinístico com tags para invalidação
        self._cache: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def select_brand_context(brand_data: Mapping[str, Any], needed_keys: Sequence[str]) -> Dict[str, Any]:
        """Recupera seletivamente apenas os atributos necessários da Brand Bible (nunca o documento inteiro)."""
        if not brand_data or not needed_keys:
            return {}
        result = {}
        for key in needed_keys:
            val = brand_data.get(key)
            if val is not None and str(val).strip():
                result[key] = str(val).strip()
        return result

    @staticmethod
    def select_product_context(product_attributes: Mapping[str, Any], needed_fields: Sequence[str]) -> Dict[str, Any]:
        """Recupera seletivamente apenas os atributos necessários da Product Bible."""
        if not product_attributes or not needed_fields:
            return {}
        result = {}
        for field in needed_fields:
            attr = product_attributes.get(field)
            if attr is None:
                continue
            if isinstance(attr, dict):
                val = attr.get('value')
                prot = attr.get('protection', 'free')
                if val is not None and str(val).strip():
                    result[field] = {'value': str(val).strip(), 'protection': prot}
            else:
                if str(attr).strip():
                    result[field] = str(attr).strip()
        return result

    @staticmethod
    def compact_context(context_dict: Mapping[str, Any]) -> Dict[str, Any]:
        """Compacta o estado estruturado removendo redundâncias e valores vazios."""
        compacted: Dict[str, Any] = {}
        for k, v in context_dict.items():
            if v is None:
                continue
            if isinstance(v, str):
                cleaned = ' '.join(v.split())
                if cleaned:
                    compacted[k] = cleaned
            elif isinstance(v, dict):
                sub = ContextOptimizer.compact_context(v)
                if sub:
                    compacted[k] = sub
            elif isinstance(v, (list, tuple)):
                cleaned_list = [x for x in v if x is not None]
                if cleaned_list:
                    compacted[k] = cleaned_list
            else:
                compacted[k] = v
        return compacted

    @staticmethod
    def enforce_context_budget(context_dict: Mapping[str, Any], max_chars: int = 1500) -> Dict[str, Any]:
        """Aplica orçamento estrito de caracteres/tokens, truncando com preservação de itens prioritários."""
        compacted = ContextOptimizer.compact_context(context_dict)
        serialized = json.dumps(compacted, ensure_ascii=False, separators=(',', ':'))
        if len(serialized) <= max_chars:
            return compacted

        # Se ultrapassar, comprime campos descritivos longos mantendo campos críticos
        result: Dict[str, Any] = dict(compacted)
        for k, v in list(result.items()):
            if isinstance(v, str) and len(v) > 80:
                result[k] = v[:77] + '...'
            elif isinstance(v, dict):
                # Mantém valor simplificado se for atributo protegido
                if 'value' in v and isinstance(v['value'], str) and len(v['value']) > 60:
                    v['value'] = v['value'][:57] + '...'

        result['context_truncated'] = True
        serialized = json.dumps(result, ensure_ascii=False, separators=(',', ':'))
        if len(serialized) > max_chars:
            # Corte agressivo em campos não críticos
            for k in list(result.keys()):
                if k not in ('label', 'logo', 'name', 'product_id'):
                    del result[k]
                    if len(json.dumps(result, ensure_ascii=False)) <= max_chars:
                        break

        return result

    def compute_cache_key(self, operation: str, prompt: str, context: Mapping[str, Any]) -> str:
        """Calcula chave de cache determinística para evitar chamadas redundantes."""
        compacted = self.compact_context(context)
        normalized = {
            'op': operation.strip().lower(),
            'prompt': ' '.join(prompt.split()),
            'context': compacted,
        }
        raw = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def get_cached(self, cache_key: str) -> Optional[Any]:
        entry = self._cache.get(cache_key)
        if not entry:
            return None
        return entry.get('value')

    def set_cached(self, cache_key: str, value: Any, entity_tags: Sequence[str] = ()) -> None:
        self._cache[cache_key] = {
            'value': value,
            'tags': set(entity_tags),
        }

    def invalidate_entity(self, entity_tag: str) -> int:
        """Invalida cache associado a uma entidade quando há nova versão oficial."""
        to_delete = [k for k, v in self._cache.items() if entity_tag in v.get('tags', set())]
        for k in to_delete:
            del self._cache[k]
        return len(to_delete)

    def clear_cache(self) -> None:
        self._cache.clear()

    def authorize_spend(
        self,
        provider: str,
        model: str,
        count: int = 1,
        custom_cost: Optional[float] = None,
    ) -> float:
        """Garante que falha ou preço desconhecido não autoriza gasto (M02-A06)."""
        if not self.cost_manager:
            raise UnknownPricingError('CostManager não configurado; gasto não autorizado.')
        return self.cost_manager.estimate_cost(provider, model, count=count, custom_cost=custom_cost)

