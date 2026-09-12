"""Busca global unificada (Seção 58).

Princípios:
- Cobre os 8 alvos: campanhas, produtos, imagens, versões, ideias, templates, decisões e histórico.
- Busca natural, semântica, case-insensitive e accent-insensitive.
- Preserva o texto original nos resultados (títulos, snippets e metadados).
- Suporta filtros por tipo de entidade.
"""
import json
import sqlite3
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set

from kiros.infrastructure.local import SQLiteDatabase


def normalize_text(text: str) -> str:
    """Normaliza texto para comparação case-insensitive e accent-insensitive.
    
    Remove diacríticos e converte para minúsculas, preservando a capacidade
    de casar termos como 'lançamento' e 'lancamento', 'Aromático' e 'aromatico'.
    """
    if not text:
        return ''
    nfkd = unicodedata.normalize('NFKD', str(text))
    ascii_only = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_only.lower().strip()


@dataclass
class SearchResult:
    entity_id: str
    entity_type: str
    type_label: str
    title: str
    snippet: str
    url: str
    score: float
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.entity_id,
            'type': self.entity_type,
            'type_label': self.type_label,
            'title': self.title,
            'snippet': self.snippet,
            'url': self.url,
            'score': round(self.score, 2),
            'metadata': self.metadata,
        }


ENTITY_TYPE_LABELS = {
    'campaign': 'Campanha',
    'product': 'Produto',
    'image': 'Imagem',
    'version': 'Versão',
    'idea': 'Ideia',
    'template': 'Template',
    'decision': 'Decisão',
    'history': 'Histórico',
}


class GlobalSearchService:
    """Serviço de busca global integrando todas as entidades do estúdio."""

    def __init__(self, database: SQLiteDatabase):
        self.db = database

    def search(
        self,
        query: str,
        entity_types: Optional[Sequence[str]] = None,
        limit: int = 40,
    ) -> List[SearchResult]:
        cleaned_query = (query or '').strip()
        if not cleaned_query:
            return []

        norm_query = normalize_text(cleaned_query)
        query_tokens = [t for t in norm_query.split() if len(t) > 1]
        if not query_tokens:
            query_tokens = [norm_query]

        allowed_types = set(entity_types) if entity_types else set(ENTITY_TYPE_LABELS.keys())
        results: List[SearchResult] = []

        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row

            if 'campaign' in allowed_types:
                results.extend(self._search_campaigns(conn, query_tokens, norm_query))
            if 'product' in allowed_types:
                results.extend(self._search_products(conn, query_tokens, norm_query))
            if 'image' in allowed_types:
                results.extend(self._search_images(conn, query_tokens, norm_query))
            if 'version' in allowed_types:
                results.extend(self._search_versions(conn, query_tokens, norm_query))
            if 'idea' in allowed_types:
                results.extend(self._search_ideas(conn, query_tokens, norm_query))
            if 'template' in allowed_types:
                results.extend(self._search_templates(conn, query_tokens, norm_query))
            if 'decision' in allowed_types:
                results.extend(self._search_decisions(conn, query_tokens, norm_query))
            if 'history' in allowed_types:
                results.extend(self._search_history(conn, query_tokens, norm_query))

        # Ordena por relevância (score decrescente)
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def _score(self, title: str, snippet: str, tokens: List[str], full_norm_query: str) -> float:
        norm_title = normalize_text(title)
        norm_snippet = normalize_text(snippet)

        score = 0.0
        # Casamento exato com a query inteira
        if full_norm_query in norm_title:
            score += 100.0
        elif full_norm_query in norm_snippet:
            score += 60.0

        # Casamento dos tokens individuais
        title_hits = sum(1 for t in tokens if t in norm_title)
        snippet_hits = sum(1 for t in tokens if t in norm_snippet)

        if title_hits == len(tokens):
            score += 40.0
        score += title_hits * 15.0

        if snippet_hits == len(tokens):
            score += 20.0
        score += snippet_hits * 5.0

        return score

    def _search_campaigns(self, conn: sqlite3.Connection, tokens: List[str], full_q: str) -> List[SearchResult]:
        rows = conn.execute('SELECT id, title, briefing_json, approval_mode, status, created_at FROM campaigns').fetchall()
        matches = []
        for r in rows:
            title = r['title']
            briefing = {}
            try:
                briefing = json.loads(r['briefing_json']) if r['briefing_json'] else {}
            except Exception:
                pass
            briefing_text = briefing.get('briefing_text', '')
            custom_objective = briefing.get('custom_objective', '')
            snippet = f"Briefing: {briefing_text} · Objetivo: {custom_objective} · Estado: {r['status']}"
            score = self._score(title, snippet, tokens, full_q)
            if score > 0:
                matches.append(SearchResult(
                    entity_id=r['id'],
                    entity_type='campaign',
                    type_label=ENTITY_TYPE_LABELS['campaign'],
                    title=title,
                    snippet=snippet,
                    url=f"/conteudo?campaign_id={r['id']}",
                    score=score,
                    metadata={'status': r['status'], 'created_at': r['created_at']},
                ))
        return matches

    def _search_products(self, conn: sqlite3.Connection, tokens: List[str], full_q: str) -> List[SearchResult]:
        rows = conn.execute('SELECT id, name, stock FROM products').fetchall()
        matches = []
        for r in rows:
            title = r['name']
            stock_info = f"Estoque: {r['stock']}" if r['stock'] is not None else "Estoque não informado"
            snippet = f"ID: {r['id']} · {stock_info}"
            score = self._score(title, snippet, tokens, full_q)
            if score > 0:
                matches.append(SearchResult(
                    entity_id=r['id'],
                    entity_type='product',
                    type_label=ENTITY_TYPE_LABELS['product'],
                    title=title,
                    snippet=snippet,
                    url=f"/marca",
                    score=score,
                    metadata={'stock': r['stock']},
                ))
        return matches

    def _search_images(self, conn: sqlite3.Connection, tokens: List[str], full_q: str) -> List[SearchResult]:
        rows = conn.execute('SELECT id, mime, product_id, scope, campaign, origin, source_reference, rights, angle FROM visual_references').fetchall()
        matches = []
        for r in rows:
            title = f"Referência {r['angle']} ({r['product_id'] or 'Geral'})"
            snippet = f"Origem: {r['origin']} · Direitos: {r['rights']} · Escopo: {r['scope']} · Fonte: {r['source_reference']}"
            score = self._score(title, snippet, tokens, full_q)
            if score > 0:
                matches.append(SearchResult(
                    entity_id=r['id'],
                    entity_type='image',
                    type_label=ENTITY_TYPE_LABELS['image'],
                    title=title,
                    snippet=snippet,
                    url=f"/biblioteca?product_id={r['product_id'] or ''}",
                    score=score,
                    metadata={'angle': r['angle'], 'rights': r['rights']},
                ))
        return matches

    def _search_versions(self, conn: sqlite3.Connection, tokens: List[str], full_q: str) -> List[SearchResult]:
        rows = conn.execute('SELECT id, campaign_id, slide_id, provider_id, model_id, prompt, reason, fidelity_score, created_at FROM execution_versions').fetchall()
        matches = []
        for r in rows:
            title = f"Versão {r['id'][:8]} · {r['provider_id']} ({r['reason']})"
            snippet = f"Prompt: {r['prompt']} · Score: {r['fidelity_score'] or 'N/A'}"
            score = self._score(title, snippet, tokens, full_q)
            if score > 0:
                matches.append(SearchResult(
                    entity_id=r['id'],
                    entity_type='version',
                    type_label=ENTITY_TYPE_LABELS['version'],
                    title=title,
                    snippet=snippet,
                    url=f"/conteudo?campaign_id={r['campaign_id']}",
                    score=score,
                    metadata={'provider': r['provider_id'], 'fidelity_score': r['fidelity_score']},
                ))
        return matches

    def _search_ideas(self, conn: sqlite3.Connection, tokens: List[str], full_q: str) -> List[SearchResult]:
        rows = conn.execute('SELECT id, title, concept, pillar, state, is_pinned, rejection_reason FROM ideas').fetchall()
        matches = []
        for r in rows:
            title = r['title']
            state = r['state']
            concept = r['concept'] or ''
            reason = r['rejection_reason'] or ''
            snippet = f"Pilar: {r['pillar']} · {concept} · Estado: {state} · Razão: {reason}"
            score = self._score(title, snippet, tokens, full_q)
            if score > 0:
                matches.append(SearchResult(
                    entity_id=r['id'],
                    entity_type='idea',
                    type_label=ENTITY_TYPE_LABELS['idea'],
                    title=title,
                    snippet=snippet,
                    url=f"/criar?pillar={r['pillar']}",
                    score=score,
                    metadata={'pillar': r['pillar'], 'state': state},
                ))
        return matches

    def _search_templates(self, conn: sqlite3.Connection, tokens: List[str], full_q: str) -> List[SearchResult]:
        rows = conn.execute('SELECT id, name, family, status, composition_rules_json, default_elements_json FROM layout_templates').fetchall()
        matches = []
        for r in rows:
            title = r['name']
            comp_rules = r['composition_rules_json'] or ''
            snippet = f"Família: {r['family']} · {comp_rules[:120]} · Status: {r['status']}"
            score = self._score(title, snippet, tokens, full_q)
            if score > 0:
                matches.append(SearchResult(
                    entity_id=r['id'],
                    entity_type='template',
                    type_label=ENTITY_TYPE_LABELS['template'],
                    title=title,
                    snippet=snippet,
                    url="/biblioteca?tab=templates",
                    score=score,
                    metadata={'family': r['family'], 'status': r['status']},
                ))
        return matches

    def _search_decisions(self, conn: sqlite3.Connection, tokens: List[str], full_q: str) -> List[SearchResult]:
        rows = conn.execute('SELECT id, decision_type, summary, details_json, created_at, provenance FROM strategic_decisions').fetchall()
        matches = []
        for r in rows:
            title = f"Decisão Estratégica: {r['decision_type']}"
            snippet = f"{r['summary']} · Origem: {r['provenance']} · Registrado em: {r['created_at']}"
            score = self._score(title, snippet, tokens, full_q)
            if score > 0:
                matches.append(SearchResult(
                    entity_id=r['id'],
                    entity_type='decision',
                    type_label=ENTITY_TYPE_LABELS['decision'],
                    title=title,
                    snippet=snippet,
                    url="/insights",
                    score=score,
                    metadata={'type': r['decision_type']},
                ))
        return matches

    def _search_history(self, conn: sqlite3.Connection, tokens: List[str], full_q: str) -> List[SearchResult]:
        matches = []

        # Custos
        cost_rows = conn.execute('SELECT id, campaign_id, stage, provider, actual_cost, timestamp FROM cost_records LIMIT 100').fetchall()
        for r in cost_rows:
            title = f"Custo registrado: {r['stage']} ({r['provider']})"
            snippet = f"Valor: R$ {r['actual_cost']:.4f} · Campanha: {r['campaign_id'] or 'Geral'} · Em: {r['timestamp']}"
            score = self._score(title, snippet, tokens, full_q)
            if score > 0:
                matches.append(SearchResult(
                    entity_id=str(r['id']),
                    entity_type='history',
                    type_label=ENTITY_TYPE_LABELS['history'],
                    title=title,
                    snippet=snippet,
                    url=f"/conteudo?campaign_id={r['campaign_id'] or ''}",
                    score=score,
                    metadata={'kind': 'cost', 'cost': r['actual_cost']},
                ))

        # Publicações no histórico
        pub_rows = conn.execute('SELECT id, campaign_id, caption, status, provider, explicit_confirmed_by, created_at FROM social_publications LIMIT 100').fetchall()
        for r in pub_rows:
            title = f"Publicação: {r['status'].capitalize()} ({r['provider']})"
            confirmed = f" por {r['explicit_confirmed_by']}" if r['explicit_confirmed_by'] else ''
            snippet = f"Campanha: {r['campaign_id'] or 'N/A'} · Status: {r['status']}{confirmed} · Legenda: {r['caption'][:80]}"
            score = self._score(title, snippet, tokens, full_q)
            if score > 0:
                matches.append(SearchResult(
                    entity_id=r['id'],
                    entity_type='history',
                    type_label=ENTITY_TYPE_LABELS['history'],
                    title=title,
                    snippet=snippet,
                    url="/calendario",
                    score=score,
                    metadata={'kind': 'publication', 'status': r['status']},
                ))

        # Aprendizados de campanha
        learn_rows = conn.execute('SELECT id, campaign_id, correction_note, created_at FROM campaign_learnings LIMIT 100').fetchall()
        for r in learn_rows:
            title = f"Aprendizado de Campanha ({r['campaign_id'][:8]})"
            snippet = f"Correção: {r['correction_note']} · Em: {r['created_at']}"
            score = self._score(title, snippet, tokens, full_q)
            if score > 0:
                matches.append(SearchResult(
                    entity_id=r['id'],
                    entity_type='history',
                    type_label=ENTITY_TYPE_LABELS['history'],
                    title=title,
                    snippet=snippet,
                    url=f"/conteudo?campaign_id={r['campaign_id']}",
                    score=score,
                    metadata={'kind': 'campaign_learning'},
                ))

        return matches
