"""CostManager: rastreamento de custos estimados e reais, controle de budget e reservas concorrentes."""
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from kiros.core.contracts import Provenance
from kiros.infrastructure.local import SQLiteDatabase
from kiros.providers.catalog import get_model_cost


class BudgetExceededError(PermissionError):
    """Lançado quando uma ação excede a política de orçamento sem aprovação."""
    pass


class UnknownPricingError(ValueError):
    """Lançado quando o preço do modelo é desconhecido ou não pode ser calculado."""
    pass


class CostManager:
    """Gerencia custos, histórico detalhado, reservas concorrentes e políticas de orçamento."""

    def __init__(self, db: SQLiteDatabase):
        self.db = db

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def set_campaign_budget(
        self,
        campaign_id: str,
        limit: float,
        alert_threshold: float = 0.8,
        allow_over_budget: bool = False,
        provenance: Optional[Provenance] = None,
    ) -> None:
        cid = (campaign_id or '').strip()
        if not cid:
            raise ValueError('ID da campanha é obrigatório.')
        if limit < 0:
            raise ValueError('Limite de orçamento deve ser maior ou igual a zero.')
        if not (0.0 < alert_threshold <= 1.0):
            raise ValueError('Limite de alerta deve estar entre 0.0 e 1.0.')

        prov_source = provenance.source if provenance else 'user'
        now = self._now()
        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''INSERT INTO campaign_budgets (campaign_id, budget_limit, alert_threshold, allow_over_budget, created_at, provenance)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(campaign_id) DO UPDATE SET
                       budget_limit=excluded.budget_limit,
                       alert_threshold=excluded.alert_threshold,
                       allow_over_budget=excluded.allow_over_budget,
                       provenance=excluded.provenance''',
                (cid, float(limit), float(alert_threshold), 1 if allow_over_budget else 0, now, prov_source),
            )

    def get_campaign_budget(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM campaign_budgets WHERE campaign_id=?', (campaign_id,)).fetchone()
            if not row:
                return None
            res = dict(row)
            res['allow_over_budget'] = bool(res['allow_over_budget'])
            return res

    def get_cost_summary(self, campaign_id: str) -> Dict[str, Any]:
        budget = self.get_campaign_budget(campaign_id) or {
            'budget_limit': 0.0,
            'alert_threshold': 0.8,
            'allow_over_budget': False,
        }
        b_limit = float(budget['budget_limit'])
        b_alert = float(budget['alert_threshold'])

        with sqlite3.connect(self.db.path) as conn:
            conn.row_factory = sqlite3.Row
            # Custo real e estimado registrados
            rows = conn.execute(
                'SELECT * FROM cost_records WHERE campaign_id=? ORDER BY id ASC', (campaign_id,)
            ).fetchall()
            records = [dict(r) for r in rows]

            # Reservas pendentes ativas
            res_row = conn.execute(
                "SELECT COALESCE(SUM(reserved_amount), 0.0) as total FROM budget_reservations WHERE campaign_id=? AND status='pending'",
                (campaign_id,),
            ).fetchone()
            reserved_total = float(res_row['total']) if res_row else 0.0

        estimated_total = sum(float(r['estimated_cost']) for r in records)
        actual_total = sum(float(r['actual_cost']) for r in records)
        generations_count = sum(int(r['generation_count']) for r in records)

        committed_or_reserved = actual_total + reserved_total
        remaining = max(0.0, b_limit - committed_or_reserved) if b_limit > 0 else 0.0
        is_alert = (committed_or_reserved >= (b_limit * b_alert)) if b_limit > 0 else False
        is_exceeded = (committed_or_reserved > b_limit) if b_limit > 0 else False

        return {
            'campaign_id': campaign_id,
            'budget_limit': b_limit,
            'alert_threshold': b_alert,
            'allow_over_budget': budget.get('allow_over_budget', False),
            'estimated_total': round(estimated_total, 4),
            'actual_total': round(actual_total, 4),
            'reserved_total': round(reserved_total, 4),
            'generations_count': generations_count,
            'remaining_budget': round(remaining, 4),
            'is_alert_triggered': is_alert,
            'is_exceeded': is_exceeded,
            'records': records,
        }

    def estimate_cost(
        self,
        provider: str,
        model: str,
        stage: str = 'generation',
        count: int = 1,
        custom_cost: Optional[float] = None,
    ) -> float:
        """Calcula estimativa de custo; recusa preço desconhecido."""
        if count <= 0:
            raise ValueError('Quantidade deve ser positiva.')

        unit_cost = get_model_cost(provider, model)
        if unit_cost is None and custom_cost is not None:
            unit_cost = custom_cost

        if unit_cost is None:
            raise UnknownPricingError(
                f"Preço desconhecido para provider '{provider}' e modelo '{model}'. "
                f"Gasto não autorizado sem precificação definida."
            )

        return round(unit_cost * count, 4)

    def plan_action(
        self,
        campaign_id: str,
        stages: List[str],
        provider: str,
        model: str,
        count: int = 1,
        custom_cost: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Avaliação prévia antes de ações caras: Plano, Custo, Impacto, Confiança, Alternativas, Aprovação."""
        cost = self.estimate_cost(provider, model, count=count, custom_cost=custom_cost)
        summary = self.get_cost_summary(campaign_id)
        b_limit = summary['budget_limit']
        current_committed = summary['actual_total'] + summary['reserved_total']
        after_action = current_committed + cost

        triggers_alert = (after_action >= (b_limit * summary['alert_threshold'])) if b_limit > 0 else False
        exceeds_budget = (after_action > b_limit) if b_limit > 0 else False

        # Alternativas de menor custo
        alternatives = []
        if provider != 'gemini' or model != 'imagen-3.0-fast-generate-001':
            fast_cost = self.estimate_cost('gemini', 'imagen-3.0-fast-generate-001', count=count)
            if fast_cost < cost:
                alternatives.append({
                    'provider': 'gemini',
                    'model': 'imagen-3.0-fast-generate-001',
                    'estimated_cost': fast_cost,
                    'savings': round(cost - fast_cost, 4),
                    'reason': 'Opção de menor custo para rascunhos.',
                })

        confidence = 0.95 if provider in ('gemini', 'openai', 'firefly') else 0.70
        requires_authorization = exceeds_budget or (triggers_alert and not summary['allow_over_budget'])

        return {
            'plan': {
                'stages': list(stages),
                'generations_count': count,
                'provider': provider,
                'model': model,
            },
            'cost': cost,
            'impact': {
                'current_spent': summary['actual_total'],
                'current_reserved': summary['reserved_total'],
                'after_action_total': round(after_action, 4),
                'budget_limit': b_limit,
                'percent_of_budget': round((after_action / b_limit * 100), 2) if b_limit > 0 else None,
                'remaining_after': round(max(0.0, b_limit - after_action), 4) if b_limit > 0 else None,
                'triggers_alert': triggers_alert,
                'exceeds_budget': exceeds_budget,
            },
            'confidence': confidence,
            'alternatives': alternatives,
            'requires_authorization': requires_authorization,
        }

    def reserve_budget(
        self,
        campaign_id: str,
        estimated_cost: float,
        approved: bool = False,
    ) -> str:
        """Reserva atomicamente o orçamento antes de execução concorrente."""
        if estimated_cost < 0:
            raise ValueError('Valor da reserva deve ser não negativo.')

        res_id = uuid.uuid4().hex
        now = self._now()

        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')

            b_row = conn.execute('SELECT * FROM campaign_budgets WHERE campaign_id=?', (campaign_id,)).fetchone()
            b_limit = float(b_row['budget_limit']) if b_row else 0.0
            allow_over = bool(b_row['allow_over_budget']) if b_row else False

            spent_row = conn.execute(
                'SELECT COALESCE(SUM(actual_cost), 0.0) as spent FROM cost_records WHERE campaign_id=?', (campaign_id,)
            ).fetchone()
            spent = float(spent_row['spent']) if spent_row else 0.0

            res_row = conn.execute(
                "SELECT COALESCE(SUM(reserved_amount), 0.0) as reserved FROM budget_reservations WHERE campaign_id=? AND status='pending'",
                (campaign_id,),
            ).fetchone()
            reserved = float(res_row['reserved']) if res_row else 0.0

            if b_limit > 0 and (spent + reserved + estimated_cost) > b_limit:
                if not (approved or allow_over):
                    conn.rollback()
                    raise BudgetExceededError(
                        f"Limite de orçamento da campanha '{campaign_id}' ultrapassado. "
                        f"Limite: ${b_limit:.4f}, Comprometido: ${spent + reserved:.4f}, "
                        f"Reserva solicitada: ${estimated_cost:.4f}. Requer aprovação explícita."
                    )

            conn.execute(
                '''INSERT INTO budget_reservations (id, campaign_id, reserved_amount, status, created_at)
                   VALUES (?, ?, ?, 'pending', ?)''',
                (res_id, campaign_id, float(estimated_cost), now),
            )
            conn.commit()

        return res_id

    def commit_reservation(
        self,
        reservation_id: str,
        actual_cost: float,
        asset_id: Optional[str],
        stage: str,
        provider: str,
        model: str,
        generation_count: int = 1,
        provenance: Optional[Provenance] = None,
    ) -> None:
        """Conclui a reserva e grava registro permanente de custo real e estimado."""
        if actual_cost < 0:
            raise ValueError('Custo real deve ser não negativo.')

        prov_source = provenance.source if provenance else 'provider'
        now = self._now()

        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')

            row = conn.execute('SELECT * FROM budget_reservations WHERE id=?', (reservation_id,)).fetchone()
            if not row:
                conn.rollback()
                raise ValueError(f"Reserva '{reservation_id}' não encontrada.")
            if row['status'] != 'pending':
                conn.rollback()
                raise ValueError(f"Reserva '{reservation_id}' já foi processada (status: {row['status']}).")

            estimated_cost = float(row['reserved_amount'])
            campaign_id = row['campaign_id']

            conn.execute("UPDATE budget_reservations SET status='committed' WHERE id=?", (reservation_id,))
            conn.execute(
                '''INSERT INTO cost_records (campaign_id, asset_id, stage, provider, model, estimated_cost, actual_cost, generation_count, timestamp, provenance)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    campaign_id,
                    asset_id,
                    stage,
                    provider,
                    model,
                    estimated_cost,
                    float(actual_cost),
                    generation_count,
                    now,
                    prov_source,
                ),
            )
            conn.commit()

    def release_reservation(self, reservation_id: str) -> None:
        """Libera reserva não utilizada (em caso de cancelamento ou falha)."""
        with sqlite3.connect(self.db.path, timeout=30.0) as conn:
            conn.execute("UPDATE budget_reservations SET status='released' WHERE id=? AND status='pending'", (reservation_id,))

    def record_direct_spend(
        self,
        campaign_id: str,
        asset_id: Optional[str],
        stage: str,
        provider: str,
        model: str,
        estimated_cost: float,
        actual_cost: float,
        generation_count: int = 1,
        provenance: Optional[Provenance] = None,
    ) -> None:
        """Registra gasto diretamente sem reserva prévia."""
        prov_source = provenance.source if provenance else 'provider'
        now = self._now()
        with sqlite3.connect(self.db.path) as conn:
            conn.execute(
                '''INSERT INTO cost_records (campaign_id, asset_id, stage, provider, model, estimated_cost, actual_cost, generation_count, timestamp, provenance)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    campaign_id,
                    asset_id,
                    stage,
                    provider,
                    model,
                    float(estimated_cost),
                    float(actual_cost),
                    generation_count,
                    now,
                    prov_source,
                ),
            )

