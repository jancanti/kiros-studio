"""Banco de ideias, pilares de conteúdo, datas sazonais e conteúdo adjacente (Seções 13, 14, 15 e 16)."""
import hashlib
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone, date
from typing import Any, Dict, List, Optional, Set

from kiros.core.contracts import Provenance
from kiros.infrastructure.local import SQLiteDatabase


INITIAL_PILLARS = ('produtos', 'lifestyle', 'marca', 'educativo', 'relacionamento', 'comercial')
MAX_ACTIVE_IDEAS_PER_PILLAR = 5

ACTIVE_STATES = {'suggested', 'approved', 'scheduled', 'pinned'}
VALID_STATES = {'suggested', 'approved', 'rejected', 'scheduled', 'published', 'archived', 'pinned'}


def _fingerprint(text: str) -> str:
    """Gera assinatura normalizada para detecção de similaridade superficial."""
    words = re.findall(r'\b[a-z0-9]{3,}\b', text.lower())
    # Remove stopwords simples
    stops = {'para', 'com', 'uma', 'como', 'sobre', 'mais', 'pelo', 'pela', 'sua', 'seu', 'este', 'esta'}
    filtered = sorted({w for w in words if w not in stops})
    return ' '.join(filtered)


class IdeaBank:
    """Gerencia o Banco de Ideias, limites por pilar, fixação, rejeição e sazonalidade."""

    def __init__(self, db: SQLiteDatabase):
        self.db = db

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def list_pillars(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('SELECT * FROM content_pillars ORDER BY weight DESC').fetchall()
            return [dict(r) for r in rows]

    def propose_new_pillar(self, name: str, reason: str, suggested_weight: float = 0.10) -> Dict[str, Any]:
        """Propõe novo pilar ('Outro'), mas nunca cria oficialmente sem aprovação (Seção 14)."""
        return {
            'proposed_name': name.strip(),
            'suggested_weight': round(suggested_weight, 2),
            'reason': reason.strip(),
            'status': 'proposal_pending_approval',
            'is_official': False,
            'requires_user_approval': True,
        }

    def count_active_ideas(self, pillar: str) -> int:
        placeholders = ','.join('?' for _ in ACTIVE_STATES)
        with sqlite3.connect(self.db.path) as conn:
            row = conn.execute(
                f'SELECT COUNT(*) FROM ideas WHERE pillar=? AND state IN ({placeholders})',
                (pillar, *ACTIVE_STATES),
            ).fetchone()
            return int(row[0]) if row else 0

    def is_superficially_similar_to_rejected(self, pillar: str, title: str, concept: str) -> Optional[str]:
        """Detecta se uma ideia é repetição superficial de uma ideia rejeitada anteriormente (Seção 16)."""
        fp_new = set(_fingerprint(f"{title} {concept}").split())
        if not fp_new:
            return None

        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT title, concept, rejection_reason, fingerprint FROM ideas WHERE pillar=? AND state='rejected'",
                (pillar,),
            ).fetchall()

            for row in rows:
                fp_old = set(row['fingerprint'].split())
                if not fp_old:
                    continue
                intersection = fp_new.intersection(fp_old)
                similarity = len(intersection) / max(len(fp_new), len(fp_old))
                if similarity >= 0.55:
                    return f"Ideia similar à anteriormente rejeitada '{row['title']}'. Motivo: {row['rejection_reason']}"
        return None

    def add_idea(
        self,
        title: str,
        concept: str,
        pillar: str,
        provenance: Optional[Provenance] = None,
        is_pinned: bool = False,
    ) -> str:
        """Adiciona ideia respeitando o limite rígido de 5 ativas por pilar e bloqueando rejeições prévias."""
        p_clean = (pillar or '').strip().lower()
        if p_clean not in INITIAL_PILLARS and p_clean != 'outro':
            raise ValueError(f"Pilar inválido: '{pillar}'. Pilares oficiais: {', '.join(INITIAL_PILLARS)}")

        # Verifica repetição superficial de rejeição
        similar_reason = self.is_superficially_similar_to_rejected(p_clean, title, concept)
        if similar_reason:
            raise ValueError(f"Reapresentação superficial impedida: {similar_reason}")

        # Verifica limite de 5 ideias ativas
        active = self.count_active_ideas(p_clean)
        if active >= MAX_ACTIVE_IDEAS_PER_PILLAR:
            raise ValueError(
                f"Limite de {MAX_ACTIVE_IDEAS_PER_PILLAR} ideias ativas atingido para o pilar '{p_clean}'. "
                f"Arquive, aprove ou descarte uma ideia antes de adicionar novas."
            )

        idea_id = uuid.uuid4().hex
        now = self._now()
        fp = _fingerprint(f"{title} {concept}")
        initial_state = 'pinned' if is_pinned else 'suggested'
        prov_source = provenance.source if provenance else 'creative_director'

        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''INSERT INTO ideas (id, title, concept, pillar, state, is_pinned, fingerprint, created_at, updated_at, provenance)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (idea_id, title.strip(), concept.strip(), p_clean, initial_state, 1 if is_pinned else 0, fp, now, now, prov_source),
            )
        return idea_id

    def pin_idea(self, idea_id: str, is_pinned: bool = True) -> None:
        """Fixa ou desafixa ideia protegendo contra arquivamento automático."""
        with sqlite3.connect(self.db.path) as conn:
            new_state = 'pinned' if is_pinned else 'suggested'
            cur = conn.execute(
                'UPDATE ideas SET is_pinned=?, state=?, updated_at=? WHERE id=?',
                (1 if is_pinned else 0, new_state, self._now(), idea_id),
            )
            if cur.rowcount == 0:
                raise ValueError(f"Ideia '{idea_id}' não encontrada.")

    def reject_idea(self, idea_id: str, reason: str) -> None:
        """Rejeita e arquiva com motivo registrado para impedir reapresentação superficial."""
        reason_clean = (reason or '').strip()
        if not reason_clean:
            raise ValueError('Motivo da rejeição é obrigatório para evitar repetições futuras.')

        with sqlite3.connect(self.db.path) as conn:
            cur = conn.execute(
                "UPDATE ideas SET state='rejected', rejection_reason=?, updated_at=? WHERE id=?",
                (reason_clean, self._now(), idea_id),
            )
            if cur.rowcount == 0:
                raise ValueError(f"Ideia '{idea_id}' não encontrada.")

    def list_ideas(self, pillar: Optional[str] = None, active_only: bool = False) -> List[Dict[str, Any]]:
        query = 'SELECT * FROM ideas WHERE 1=1'
        params: List[Any] = []
        if pillar:
            query += ' AND pillar = ?'
            params.append(pillar.lower())
        if active_only:
            placeholders = ','.join('?' for _ in ACTIVE_STATES)
            query += f' AND state IN ({placeholders})'
            params.extend(ACTIVE_STATES)
        query += ' ORDER BY is_pinned DESC, updated_at DESC'

        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, tuple(params)).fetchall()
            result = []
            for r in rows:
                item = dict(r)
                item['is_pinned'] = bool(item['is_pinned'])
                result.append(item)
            return result

    @staticmethod
    def generate_adjacent_content_suggestions(topic: str) -> List[Dict[str, Any]]:
        """Gera ideias adjacentes à categoria da marca explicando público, relação e ponte (Seção 13)."""
        cleaned_topic = (topic or 'desaceleração').strip().lower()

        templates = [
            {
                'title': f'Ritual Noturno e Desconexão Digital ({cleaned_topic})',
                'why_attracts_audience': 'Público busca refúgio contra sobrecarga digital e insônia ao fim do dia.',
                'relation_to_brand': 'A atmosfera de tranquilidade e aconchego olfativo é a identidade central da KIROS.',
                'bridge_to_brand': 'Substituir telas por 15 minutos de silêncio e acender a vela aromática para ancorar o descanso.',
                'pillar': 'lifestyle',
                'funnel_stage': 'Descoberta',
            },
            {
                'title': f'Estética e Organização Minimalista ({cleaned_topic})',
                'why_attracts_audience': 'Interesse por design editorial, ordem visual e sensação de paz no lar.',
                'relation_to_brand': 'Frascos em vidro fosco e tampas em madeira nobre funcionam como objetos de arte.',
                'bridge_to_brand': 'Apresentar a vela como ponto focal de composição na mesa de centro ou aparador.',
                'pillar': 'lifestyle',
                'funnel_stage': 'Descoberta',
            },
            {
                'title': f'Guia Botânico: A Arte das Notas de Fundo ({cleaned_topic})',
                'why_attracts_audience': 'Curiosidade sobre aromacologia e como notas olfativas alteram a percepção do espaço.',
                'relation_to_brand': 'A KIROS compõe aromas em camadas complexas (topo cítrico, corpo floral e fundo amadeirado).',
                'bridge_to_brand': 'Explicar a evolução do aroma do difusor ao longo das semanas no ambiente.',
                'pillar': 'educativo',
                'funnel_stage': 'Interesse',
            },
        ]
        return templates

    @staticmethod
    def get_seasonal_opportunities(reference_date: Optional[date] = None) -> List[Dict[str, Any]]:
        """Identifica oportunidades sazonais 2-3 meses antes, sem oficializar calendário (Seção 15)."""
        ref = reference_date or datetime.now(timezone.utc).date()
        year = ref.year

        # Datas prioritárias da Seção 15: Natal (25/12) e Dia das Mães (2º domingo de maio)
        natal = date(year, 12, 25)
        if natal < ref:
            natal = date(year + 1, 12, 25)

        # Dia das mães: segundo domingo de maio
        may_first = date(year, 5, 1)
        first_sun = 1 + (6 - may_first.weekday()) % 7
        dia_das_maes = date(year, 5, first_sun + 7)
        if dia_das_maes < ref:
            may_first_next = date(year + 1, 5, 1)
            first_sun_next = 1 + (6 - may_first_next.weekday()) % 7
            dia_das_maes = date(year + 1, 5, first_sun_next + 7)

        events = [
            {'name': 'Natal', 'date': natal},
            {'name': 'Dia das Mães', 'date': dia_das_maes},
        ]

        opportunities = []
        for ev in events:
            days_until = (ev['date'] - ref).days
            # Planejamento aproximadamente 2-3 meses antes (entre 45 e 100 dias)
            in_planning_window = 45 <= days_until <= 100
            current_phase = 'Warm-up' if days_until > 60 else ('Consideração' if days_until > 30 else 'Conversão')

            opportunities.append({
                'event_name': ev['name'],
                'target_date': ev['date'].isoformat(),
                'days_until': days_until,
                'in_planning_window': in_planning_window,
                'current_phase': current_phase,
                'is_draft': True,
                'in_official_calendar': False,  # Não entra no calendário oficial sem aprovação
                'phases': [
                    {'phase': 'Warm-up', 'goal': 'Desejo e antecipação de presentes olfativos'},
                    {'phase': 'Consideração', 'goal': 'Apresentação de kits exclusivos e combinações'},
                    {'phase': 'Conversão', 'goal': 'Garantia de entrega e edições limitadas'},
                    {'phase': 'Last Call', 'goal': 'Última oportunidade para entregas antes da data'},
                ],
            })
        return opportunities

