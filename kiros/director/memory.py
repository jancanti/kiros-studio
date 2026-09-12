"""Memória tipada, recuperação seletiva e detecção de conflitos (Seções 48 e 49)."""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from kiros.core.contracts import Provenance
from kiros.infrastructure.local import SQLiteDatabase


VALID_MEMORY_TYPES = (
    'campaign_context',
    'recurring_preference',
    'brand_rule',
    'commercial_data',
    'creative_decision',
    'operational_setting',
)


class ConflictReport:
    """Relatório estruturado de divergência entre dados propostos e oficiais."""

    def __init__(
        self,
        field: str,
        official_value: Any,
        candidate_value: Any,
        official_source: str,
        candidate_source: str,
        confidence: float,
        recommendation: str,
        is_high_impact: bool,
    ):
        self.field = field
        self.official_value = official_value
        self.candidate_value = candidate_value
        self.official_source = official_source
        self.candidate_source = candidate_source
        self.confidence = confidence
        self.recommendation = recommendation
        self.is_high_impact = is_high_impact

    def to_dict(self) -> Dict[str, Any]:
        return {
            'field': self.field,
            'official_value': self.official_value,
            'candidate_value': self.candidate_value,
            'official_source': self.official_source,
            'candidate_source': self.candidate_source,
            'confidence': round(self.confidence, 2),
            'recommendation': self.recommendation,
            'is_high_impact': self.is_high_impact,
        }


class MemoryStore:
    """Gerencia memórias tipadas persistentes com proveniência e recuperação seletiva."""

    def __init__(self, db: SQLiteDatabase):
        self.db = db

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def store_memory(
        self,
        memory_type: str,
        key: str,
        value: str,
        scope: str = 'global',
        confidence: float = 1.0,
        provenance: Optional[Provenance] = None,
    ) -> str:
        if memory_type not in VALID_MEMORY_TYPES:
            raise ValueError(f"Tipo de memória inválido: '{memory_type}'. Suportados: {', '.join(VALID_MEMORY_TYPES)}")
        cleaned_key = (key or '').strip()
        if not cleaned_key:
            raise ValueError('Chave da memória não pode ser vazia.')

        mem_id = uuid.uuid4().hex
        prov_source = provenance.source if provenance else 'user'
        now = self._now()

        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''INSERT INTO typed_memories (id, memory_type, key, value, scope, confidence, created_at, provenance)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (mem_id, memory_type, cleaned_key, str(value), scope, float(confidence), now, prov_source),
            )
        return mem_id

    def query_memories(
        self,
        memory_types: Optional[Sequence[str]] = None,
        scope: Optional[str] = None,
        keys: Optional[Sequence[str]] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Recuperação seletiva de memória relevante: não carrega tudo indiscriminadamente."""
        query = 'SELECT * FROM typed_memories WHERE 1=1'
        params: List[Any] = []

        if memory_types:
            placeholders = ','.join('?' for _ in memory_types)
            query += f' AND memory_type IN ({placeholders})'
            params.extend(memory_types)

        if scope:
            query += ' AND (scope = ? OR scope = "global")'
            params.append(scope)

        if keys:
            placeholders = ','.join('?' for _ in keys)
            query += f' AND key IN ({placeholders})'
            params.extend(keys)

        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)

        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(r) for r in rows]

    def retrieve_relevant_context(
        self,
        memory_types: Optional[Sequence[str]] = None,
        scope: Optional[str] = None,
        keys: Optional[Sequence[str]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Recuperação seletiva de memória relevante para a tarefa (Seção 48 e M03-A05)."""
        return self.query_memories(memory_types=memory_types, scope=scope, keys=keys, limit=limit)

    def compact_memories(
        self,
        memories: Sequence[Dict[str, Any]],
        max_chars: int = 1500,
    ) -> Dict[str, Any]:
        """Compacta memórias tipadas recuperadas para economizar tokens, removendo redundâncias (M03-A05)."""
        compacted: Dict[str, Any] = {}
        for m in memories:
            k = m.get('key')
            v = m.get('value')
            if not k or v is None:
                continue
            cleaned_v = ' '.join(str(v).split())
            compacted[k] = {
                'value': cleaned_v,
                'type': m.get('memory_type'),
                'confidence': m.get('confidence', 1.0),
                'provenance': m.get('provenance', 'unknown'),
            }
        serialized = json.dumps(compacted, ensure_ascii=False)
        if len(serialized) > max_chars:
            for item in compacted.values():
                if isinstance(item, dict) and 'value' in item and len(item['value']) > 60:
                    item['value'] = item['value'][:57] + '...'
        return compacted

    def record_decision(
        self,
        decision_type: str,
        summary: str,
        details: Dict[str, Any],
        provenance: Provenance,
    ) -> str:
        """Registra decisões estratégicas com proveniência obrigatória."""
        dec_id = uuid.uuid4().hex
        now = self._now()
        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''INSERT INTO strategic_decisions (id, decision_type, summary, details_json, created_at, provenance)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (dec_id, decision_type, summary, json.dumps(details, ensure_ascii=False), now, provenance.source),
            )
        return dec_id

    def detect_conflicts(
        self,
        candidate_data: Dict[str, Any],
        official_brand: Dict[str, Any],
        official_product: Optional[Dict[str, Any]] = None,
        candidate_source: str = 'user_briefing',
    ) -> List[ConflictReport]:
        """Detecta conflitos entre dados candidatos e a fonte de verdade oficial.
        
        Princípio da Seção 49: Nunca sobrescrever automaticamente informação oficial.
        """
        conflicts: List[ConflictReport] = []

        # 1. Conflitos com Brand Bible
        for k, cand_val in candidate_data.items():
            if k in official_brand and official_brand[k]:
                off_val = official_brand[k]
                # Se ambos definidos e divergentes
                if str(cand_val).strip().lower() != str(off_val).strip().lower():
                    is_critical = k in ('colors', 'fonts', 'voice', 'values')
                    rec = (
                        f"Manter diretriz oficial da Brand Bible ({off_val}) para consistência de marca."
                        if is_critical
                        else f"Avaliar se a sugestão '{cand_val}' aplica-se como override isolado de campanha."
                    )
                    conflicts.append(ConflictReport(
                        field=f"brand.{k}",
                        official_value=off_val,
                        candidate_value=cand_val,
                        official_source="brand_bible",
                        candidate_source=candidate_source,
                        confidence=0.95,
                        recommendation=rec,
                        is_high_impact=is_critical,
                    ))

        # 2. Conflitos com Product Bible (atributos críticos e protegidos)
        if official_product:
            prod_attrs = official_product.get('attributes', {})
            for attr_name, cand_val in candidate_data.items():
                if attr_name in prod_attrs:
                    attr_obj = prod_attrs[attr_name]
                    off_val = attr_obj.get('value') if isinstance(attr_obj, dict) else attr_obj
                    prot = attr_obj.get('protection', 'free') if isinstance(attr_obj, dict) else 'free'
                    if off_val and str(cand_val).strip().lower() != str(off_val).strip().lower():
                        is_critical = prot in ('critical', 'protected')
                        rec = (
                            f"Atributo {prot} '{attr_name}' não pode ser alterado automaticamente. Manter '{off_val}'."
                            if is_critical
                            else f"Permitir variação criativa '{cand_val}' no contexto da campanha."
                        )
                        conflicts.append(ConflictReport(
                            field=f"product.{attr_name}",
                            official_value=off_val,
                            candidate_value=cand_val,
                            official_source="product_bible",
                            candidate_source=candidate_source,
                            confidence=0.90,
                            recommendation=rec,
                            is_high_impact=is_critical,
                        ))

        return conflicts
