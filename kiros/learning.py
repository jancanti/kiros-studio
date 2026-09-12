"""Módulo de Aprendizado e Prompt Library (Seções 47 e 55).

Princípios:
- Correção de campanha gera aprendizado local.
- Preferências repetidas geram sugestões de preferência.
- Novas regras e mudanças de produto viram propostas (Brand Bible / Product Bible).
- Nenhuma alteração permanente ou prompt salvo sem aprovação explícita com responsável.
"""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from kiros.core.contracts import Provenance
from kiros.infrastructure.local import SQLiteDatabase


class PromptLibrary:
    """Biblioteca de Prompts com curadoria (Seção 55).
    
    Prompts com bons desempenhos são sugeridos e só são salvos permanentemente
    após aprovação explícita.
    """

    def __init__(self, database: SQLiteDatabase):
        self.db = database

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def suggest_prompt(
        self,
        title: str,
        objective: str,
        engine: str,
        context: str,
        prompt_text: str,
        result_summary: str,
        performance_score: float = 0.0,
        provenance: Optional[Provenance] = None,
    ) -> str:
        """Sugere um prompt com bom resultado (status: suggested)."""
        if not title or not title.strip():
            raise ValueError('Título do prompt é obrigatório.')
        if not objective or not objective.strip():
            raise ValueError('Objetivo do prompt é obrigatório.')
        if not engine or not engine.strip():
            raise ValueError('Engine do prompt é obrigatória.')
        if not prompt_text or not prompt_text.strip():
            raise ValueError('Texto do prompt é obrigatório.')

        prompt_id = uuid.uuid4().hex
        prov_str = provenance.source if provenance else 'system_recommendation'
        now = self._now()

        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''INSERT INTO prompt_library (
                    id, title, objective, engine, context, prompt_text,
                    result_summary, performance_score, status, approved_by,
                    approved_at, provenance, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'suggested', NULL, NULL, ?, ?)''',
                (
                    prompt_id,
                    title.strip(),
                    objective.strip(),
                    engine.strip(),
                    (context or '').strip(),
                    prompt_text.strip(),
                    (result_summary or '').strip(),
                    float(performance_score),
                    prov_str,
                    now,
                ),
            )
        return prompt_id

    def approve_prompt(self, prompt_id: str, approver: str) -> Dict[str, Any]:
        """Aprova permanentemente um prompt sugerido na biblioteca."""
        if not approver or not approver.strip():
            raise ValueError('Responsável pela aprovação do prompt é obrigatório.')

        now = self._now()
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM prompt_library WHERE id = ?', (prompt_id,)).fetchone()
            if not row:
                raise ValueError(f'Prompt não encontrado: {prompt_id}')
            if row['status'] == 'approved':
                raise ValueError('Prompt já está aprovado.')

            conn.execute(
                'UPDATE prompt_library SET status = "approved", approved_by = ?, approved_at = ? WHERE id = ?',
                (approver.strip(), now, prompt_id),
            )
            updated = conn.execute('SELECT * FROM prompt_library WHERE id = ?', (prompt_id,)).fetchone()
            return dict(updated)

    def archive_prompt(self, prompt_id: str) -> None:
        with sqlite3.connect(self.db.path) as conn:
            conn.execute('UPDATE prompt_library SET status = "archived" WHERE id = ?', (prompt_id,))

    def get_prompt(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM prompt_library WHERE id = ?', (prompt_id,)).fetchone()
            return dict(row) if row else None

    def list_prompts(
        self,
        status: Optional[str] = None,
        objective: Optional[str] = None,
        engine: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        query = 'SELECT * FROM prompt_library WHERE 1=1'
        params: List[Any] = []
        if status:
            query += ' AND status = ?'
            params.append(status)
        if objective:
            query += ' AND objective LIKE ?'
            params.append(f'%{objective}%')
        if engine:
            query += ' AND engine = ?'
            params.append(engine)
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)

        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(r) for r in rows]


class LearningService:
    """Serviço central de aprendizado (Seção 47).
    
    Orquestra correções de campanhas, sugestões de preferências, conflitos e
    propostas para Brand Bible e Product Bible.
    """

    def __init__(self, database: SQLiteDatabase, library, memory_store):
        self.db = database
        self.library = library
        self.memory = memory_store

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def record_campaign_correction(
        self,
        campaign_id: str,
        correction_note: str,
        slide_id: Optional[str] = None,
        source: str = 'user',
        category: str = 'correction',
    ) -> str:
        """Registra uma correção manual em campanha como aprendizado local (Seção 47)."""
        if not correction_note or not correction_note.strip():
            raise ValueError('Nota de correção é obrigatória.')
        if not campaign_id or not campaign_id.strip():
            raise ValueError('Identificador da campanha é obrigatório.')

        learning_id = uuid.uuid4().hex
        now = self._now()
        prov_str = f'campaign_correction:{source}'

        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''INSERT INTO campaign_learnings (id, campaign_id, slide_id, correction_note, category, created_at, provenance)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (learning_id, campaign_id.strip(), slide_id, correction_note.strip(), category, now, prov_str),
            )

            # Verifica se essa mesma correção ou tema se repete em múltiplas campanhas
            # Se ocorrer 2 ou mais vezes, sugere como recurring_preference
            note_sample = correction_note.strip().lower()[:40]
            count = conn.execute(
                "SELECT COUNT(*) FROM campaign_learnings WHERE lower(correction_note) LIKE ?",
                (f'%{note_sample}%',),
            ).fetchone()[0]

            if count >= 2:
                # Cria sugestão de preferência repetida (não permanente!)
                self._maybe_create_recurring_preference_proposal(
                    conn,
                    key=f'pref_{learning_id[:8]}',
                    summary=f'Preferência repetida ({count} ocorrências): {correction_note.strip()[:80]}',
                    details={'full_note': correction_note.strip(), 'evidence_count': count},
                    provenance=Provenance('automatic_analysis', f'detected_from_{count}_corrections', now),
                )

        return learning_id

    def _maybe_create_recurring_preference_proposal(
        self,
        conn: sqlite3.Connection,
        key: str,
        summary: str,
        details: Dict[str, Any],
        provenance: Provenance,
    ) -> None:
        # Evita duplicar proposta pendente idêntica
        existing = conn.execute(
            "SELECT 1 FROM learning_proposals WHERE kind = 'recurring_preference' AND summary = ? AND status = 'suggested'",
            (summary,),
        ).fetchone()
        if existing:
            return

        prop_id = uuid.uuid4().hex
        now = self._now()
        conn.execute(
            '''INSERT INTO learning_proposals (
                id, kind, target_type, target_id, summary, details_json,
                evidence_count, status, approved_by, approved_at, provenance, created_at
            ) VALUES (?, 'recurring_preference', 'preference', ?, ?, ?, ?, 'suggested', NULL, NULL, ?, ?)''',
            (prop_id, key, summary, json.dumps(details, ensure_ascii=False), details.get('evidence_count', 2), provenance.source, now),
        )

    def suggest_recurring_preference(
        self,
        key: str,
        value: str,
        reason: str,
        provenance: Optional[Provenance] = None,
        evidence_count: int = 1,
    ) -> str:
        """Propõe uma preferência repetida observada pelo sistema (status: suggested)."""
        if not key or not key.strip():
            raise ValueError('Chave da preferência é obrigatória.')
        if not value or not value.strip():
            raise ValueError('Valor da preferência é obrigatório.')

        prop_id = uuid.uuid4().hex
        now = self._now()
        prov_str = provenance.source if provenance else 'user_observation'
        details = {'key': key.strip(), 'value': value.strip(), 'reason': reason.strip()}

        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''INSERT INTO learning_proposals (
                    id, kind, target_type, target_id, summary, details_json,
                    evidence_count, status, approved_by, approved_at, provenance, created_at
                ) VALUES (?, 'recurring_preference', 'preference', ?, ?, ?, ?, 'suggested', NULL, NULL, ?, ?)''',
                (
                    prop_id,
                    key.strip(),
                    f'Preferência: {key.strip()} = {value.strip()}',
                    json.dumps(details, ensure_ascii=False),
                    int(evidence_count),
                    prov_str,
                    now,
                ),
            )
        return prop_id

    def propose_brand_rule(
        self,
        rule_name: str,
        rule_value: str,
        reason: str,
        provenance: Optional[Provenance] = None,
    ) -> str:
        """Cria proposta de nova regra de marca (proposta de Brand Bible, Seção 47)."""
        if not rule_name or not rule_name.strip():
            raise ValueError('Nome da regra é obrigatório.')
        if not rule_value or not rule_value.strip():
            raise ValueError('Valor da regra é obrigatório.')

        prop_id = uuid.uuid4().hex
        now = self._now()
        prov_str = provenance.source if provenance else 'user_suggestion'
        details = {'rule_name': rule_name.strip(), 'rule_value': rule_value.strip(), 'reason': reason.strip()}

        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''INSERT INTO learning_proposals (
                    id, kind, target_type, target_id, summary, details_json,
                    evidence_count, status, approved_by, approved_at, provenance, created_at
                ) VALUES (?, 'brand_rule', 'brand', 'global', ?, ?, 1, 'suggested', NULL, NULL, ?, ?)''',
                (
                    prop_id,
                    f'Regra de Marca: {rule_name.strip()} ({reason.strip()})',
                    json.dumps(details, ensure_ascii=False),
                    prov_str,
                    now,
                ),
            )
        return prop_id

    def propose_product_change(
        self,
        product_id: str,
        attributes: Dict[str, Any],
        reason: str,
        provenance: Optional[Provenance] = None,
    ) -> str:
        """Cria proposta de mudança de produto (proposta de Product Bible, Seção 47)."""
        if not product_id or not product_id.strip():
            raise ValueError('Identificador do produto é obrigatório.')
        if not attributes or not isinstance(attributes, dict):
            raise ValueError('Atributos de produto são obrigatórios.')

        prop_id = uuid.uuid4().hex
        now = self._now()
        prov_str = provenance.source if provenance else 'user_suggestion'
        details = {'product_id': product_id.strip(), 'attributes': attributes, 'reason': reason.strip()}

        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''INSERT INTO learning_proposals (
                    id, kind, target_type, target_id, summary, details_json,
                    evidence_count, status, approved_by, approved_at, provenance, created_at
                ) VALUES (?, 'product_change', 'product', ?, ?, ?, 1, 'suggested', NULL, NULL, ?, ?)''',
                (
                    prop_id,
                    product_id.strip(),
                    f'Atualização de Produto {product_id.strip()}: {reason.strip()}',
                    json.dumps(details, ensure_ascii=False),
                    prov_str,
                    now,
                ),
            )
        return prop_id

    def approve_proposal(
        self,
        proposal_id: str,
        approver: str,
        confirm_protected: bool = False,
    ) -> Dict[str, Any]:
        """Aprova formalmente uma proposta de aprendizado, aplicando-a permanentemente."""
        if not approver or not approver.strip():
            raise ValueError('Responsável pela aprovação é obrigatório.')

        now = self._now()
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM learning_proposals WHERE id = ?', (proposal_id,)).fetchone()
            if not row:
                raise ValueError(f'Proposta não encontrada: {proposal_id}')
            if row['status'] == 'approved':
                raise ValueError('Proposta já aprovada anteriormente.')

            details = json.loads(row['details_json'])
            kind = row['kind']

            # Aplicação oficial de acordo com o tipo
            if kind == 'recurring_preference':
                key = details.get('key') or row['target_id']
                val = details.get('value') or details.get('full_note', '')
                if self.memory:
                    self.memory.store_memory(
                        memory_type='recurring_preference',
                        key=key,
                        value=val,
                        scope='global',
                        provenance=Provenance('user', f'approved_by:{approver.strip()}', now),
                    )
            elif kind == 'brand_rule':
                rule_name = details.get('rule_name')
                rule_val = details.get('rule_value')
                if self.memory and rule_name and rule_val:
                    self.memory.store_memory(
                        memory_type='brand_rule',
                        key=rule_name,
                        value=rule_val,
                        scope='global',
                        provenance=Provenance('user', f'approved_by:{approver.strip()}', now),
                    )
            elif kind == 'product_change':
                prod_id = details.get('product_id') or row['target_id']
                attrs = details.get('attributes', {})
                if self.library and attrs:
                    # Cria proposta oficial na Product Bible para ser versionada
                    self.library.propose(
                        'product',
                        prod_id,
                        attrs,
                        source=f'Aprovado de proposta de aprendizado {proposal_id} por {approver.strip()}',
                        source_kind='user',
                    )

            conn.execute(
                'UPDATE learning_proposals SET status = "approved", approved_by = ?, approved_at = ? WHERE id = ?',
                (approver.strip(), now, proposal_id),
            )
            updated = conn.execute('SELECT * FROM learning_proposals WHERE id = ?', (proposal_id,)).fetchone()
            return dict(updated)

    def reject_proposal(self, proposal_id: str, reviewer: str, reason: str = '') -> None:
        now = self._now()
        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                'UPDATE learning_proposals SET status = "rejected", approved_by = ?, approved_at = ? WHERE id = ?',
                (reviewer.strip() if reviewer else 'user', now, proposal_id),
            )

    def list_proposals(
        self,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        query = 'SELECT * FROM learning_proposals WHERE 1=1'
        params: List[Any] = []
        if kind:
            query += ' AND kind = ?'
            params.append(kind)
        if status:
            query += ' AND status = ?'
            params.append(status)
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)

        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(r) for r in rows]

    def list_learnings(self, campaign_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        query = 'SELECT * FROM campaign_learnings WHERE 1=1'
        params: List[Any] = []
        if campaign_id:
            query += ' AND campaign_id = ?'
            params.append(campaign_id)
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)

        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(r) for r in rows]

    def summary(self) -> Dict[str, Any]:
        with sqlite3.connect(self.db.path) as conn:
            corrections_count = conn.execute('SELECT COUNT(*) FROM campaign_learnings').fetchone()[0]
            proposals_pending = conn.execute("SELECT COUNT(*) FROM learning_proposals WHERE status = 'suggested'").fetchone()[0]
            proposals_approved = conn.execute("SELECT COUNT(*) FROM learning_proposals WHERE status = 'approved'").fetchone()[0]
            prompts_approved = conn.execute("SELECT COUNT(*) FROM prompt_library WHERE status = 'approved'").fetchone()[0]
            prompts_suggested = conn.execute("SELECT COUNT(*) FROM prompt_library WHERE status = 'suggested'").fetchone()[0]
            return {
                'total_corrections': corrections_count,
                'pending_proposals': proposals_pending,
                'approved_proposals': proposals_approved,
                'approved_prompts': prompts_approved,
                'suggested_prompts': prompts_suggested,
            }
