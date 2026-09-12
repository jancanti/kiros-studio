"""Serviço central de checagem de fidelidade de produto (Seções 27, 78 e M06)."""
from datetime import datetime, timezone
import json
import sqlite3
from typing import Any, Dict, List, Optional
import uuid

from kiros.cost import CostManager
from kiros.director.memory import MemoryStore
from kiros.fidelity.fixtures import FIXTURE_CORRECT_PRODUCT
from kiros.fidelity.models import (
    FIDELITY_DIMENSIONS,
    VALID_FIDELITY_MODES,
    FidelityCheckResult,
    FidelityDimensionResult,
    FidelityDiscrepancy,
)
from kiros.infrastructure.local import FileStorage, SQLiteDatabase
from kiros.library import Library


class ProductFidelityService:
    """Implementa o ProductFidelityService (Seção 27 da especificação).

    Avalia fidelidade de assets gerados comparando com referências reais de produto
    e atributos críticos da Product Bible. O score é explicitamente uma estimativa
    de visão computacional determinística em ambiente mock.
    """

    DEFAULT_THRESHOLD = 85.0
    DEFAULT_MODE = 'recommend_before_spend'

    def __init__(
        self,
        database: SQLiteDatabase,
        library: Library,
        cost_manager: CostManager,
        storage: Optional[FileStorage] = None,
        memory_store: Optional[MemoryStore] = None,
    ):
        self.database = database
        self.library = library
        self.cost_manager = cost_manager
        self.storage = storage
        self.memory_store = memory_store

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def set_campaign_fidelity_config(
        self,
        campaign_id: str,
        mode: str = DEFAULT_MODE,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        """Configura o modo de fidelidade e threshold da campanha (Seção 27)."""
        if mode not in VALID_FIDELITY_MODES:
            raise ValueError(f"Modo de fidelidade inválido: '{mode}'. Suportados: {', '.join(VALID_FIDELITY_MODES)}")
        if not (0.0 <= float(threshold) <= 100.0):
            raise ValueError('Threshold de fidelidade deve estar entre 0 e 100.')

        with sqlite3.connect(self.database.path) as conn:
            conn.execute(
                'UPDATE campaigns SET fidelity_mode=?, fidelity_threshold=?, updated_at=? WHERE id=?',
                (mode, float(threshold), self._now(), campaign_id),
            )

    def get_campaign_fidelity_config(self, campaign_id: str) -> Dict[str, Any]:
        with sqlite3.connect(self.database.path) as conn:
            row = conn.execute(
                'SELECT fidelity_mode, fidelity_threshold FROM campaigns WHERE id=?',
                (campaign_id,),
            ).fetchone()
            if not row:
                return {'mode': self.DEFAULT_MODE, 'threshold': self.DEFAULT_THRESHOLD}
            return {
                'mode': row[0] or self.DEFAULT_MODE,
                'threshold': float(row[1] if row[1] is not None else self.DEFAULT_THRESHOLD),
            }

    def check_fidelity(
        self,
        campaign_id: str,
        product_id: str,
        asset_id: str,
        slide_id: Optional[str] = None,
        version_id: Optional[str] = None,
        fixture_override: Optional[Dict[str, Any]] = None,
        threshold_override: Optional[float] = None,
        mode_override: Optional[str] = None,
        provider_id: str = 'gemini',
        model_id: str = 'imagen-3.0-generate-002',
    ) -> FidelityCheckResult:
        """Executa a checagem de fidelidade conforme a Seção 27 da especificação."""
        config = self.get_campaign_fidelity_config(campaign_id)
        mode = mode_override or config['mode']
        threshold = float(threshold_override if threshold_override is not None else config['threshold'])

        if mode not in VALID_FIDELITY_MODES:
            raise ValueError(f"Modo de fidelidade inválido: '{mode}'")

        # 1. Recupera referências visuais reais do produto (Seção 78)
        visual_refs = []
        try:
            visual_refs = self.library.reference_set(product_id, 'catalog', campaign=campaign_id)
        except Exception:
            # Fallback seguro se não houver referências de catálogo
            visual_refs = []

        # 2. Recupera atributos da Product Bible oficial
        product_info = self.library.product(product_id)
        product_attributes = product_info.get('attributes', {}) if product_info else {}

        # 3. Utiliza fixture especificada ou baseline de produto correto
        features = fixture_override if fixture_override is not None else FIXTURE_CORRECT_PRODUCT

        # Pesos das 7 dimensões físicas da Seção 27
        weights = {
            'shape': 1.0,
            'proportion': 1.0,
            'cap': 1.0,
            'label': 1.5,
            'logo': 2.0,  # Logo da marca possui alto peso de preservação
            'colors': 1.0,
            'material': 1.0,
        }

        dimension_results: Dict[str, FidelityDimensionResult] = {}
        discrepancies: List[FidelityDiscrepancy] = []
        total_weighted_score = 0.0
        total_weights = 0.0
        critical_failed = False

        for dim, weight in weights.items():
            feat = features.get(dim, {'score': 95.0, 'status': 'match', 'detected': 'Conforme referência'})
            dim_score = float(feat.get('score', 95.0))
            status = feat.get('status', 'match')
            detected = feat.get('detected', 'Conforme referência')

            # Atributo correspondente na Product Bible
            pb_attr = product_attributes.get(dim, {})
            expected = pb_attr.get('value', 'Especificação oficial da Product Bible')
            protection = pb_attr.get('protection', 'protected' if dim in ('label', 'logo') else 'free')

            dim_discrepancies: List[FidelityDiscrepancy] = []
            if status != 'match' or dim_score < threshold:
                disc_msg = feat.get('discrepancy') or f"Divergência detectada no atributo '{dim}': esperado '{expected}', detectado '{detected}'."
                disc = FidelityDiscrepancy(
                    dimension=dim,
                    attribute=dim,
                    expected=expected,
                    detected=detected,
                    severity=protection,
                    explanation=disc_msg,
                )
                dim_discrepancies.append(disc)
                discrepancies.append(disc)

                if protection == 'critical' and dim_score < 70.0:
                    critical_failed = True

            dimension_results[dim] = FidelityDimensionResult(
                dimension=dim,
                score=dim_score,
                weight=weight,
                status=status,
                discrepancies=dim_discrepancies,
            )

            total_weighted_score += dim_score * weight
            total_weights += weight

        # Dimensão 8: Atributos Críticos consolidados
        crit_attrs = [k for k, v in product_attributes.items() if v.get('protection') == 'critical']
        crit_score = 40.0 if critical_failed else 95.0
        crit_status = 'divergent' if critical_failed else 'match'
        dimension_results['critical_attributes'] = FidelityDimensionResult(
            dimension='critical_attributes',
            score=crit_score,
            weight=1.5,
            status=crit_status,
            discrepancies=[d for d in discrepancies if d.severity == 'critical'],
        )
        total_weighted_score += crit_score * 1.5
        total_weights += 1.5

        # Score global ponderado (0.0 a 100.0)
        final_score = round(total_weighted_score / total_weights, 1)

        # Regra de aprovação da fidelidade
        passed = (final_score >= threshold) and not critical_failed

        # Status geral do check
        if passed:
            status = 'passed'
            approval_status = 'none'
            suggested_fix = None
            estimated_cost = 0.0
        else:
            status = 'warn' if mode == 'warn_only' else 'failed'
            # Seção 27: Quando falhar: Explicar problema -> Sugerir correção -> Estimar custo -> Solicitar aprovação
            # Estimativa de custo de regeneração
            try:
                estimated_cost = self.cost_manager.estimate_cost(provider_id, model_id, {})
            except Exception:
                estimated_cost = 0.16

            # Elabora sugestão de correção orientada aos problemas detectados
            failed_dims = [d.dimension for d in discrepancies]
            sugg_parts = []
            if 'logo' in failed_dims:
                sugg_parts.append("Reforçar logotipo oficial e posicionamento na parte frontal")
            if 'label' in failed_dims:
                sugg_parts.append("Ajustar nitidez da etiqueta e preservar tipografia sem distorções")
            if 'cap' in failed_dims or 'material' in failed_dims:
                sugg_parts.append("Especificar material exato e textura da tampa e do frasco")
            if 'shape' in failed_dims or 'proportion' in failed_dims:
                sugg_parts.append("Restringir proporções da silhueta utilizando imagens de catálogo como guia rígido")
            if not sugg_parts:
                sugg_parts.append("Ajustar prompt negativo para remover artefatos e variações não oficiais")

            suggested_fix = "Correção sugerida para o prompt: " + "; ".join(sugg_parts) + "."

            if mode == 'recommend_before_spend':
                approval_status = 'pending'
            elif mode == 'auto_regenerate':
                # Verifica orçamento e limite de tentativas antes de autorizar auto-regeneração (M06-A02)
                budget_ok = self.cost_manager.check_budget(campaign_id, estimated_cost)
                if budget_ok:
                    approval_status = 'auto_applied'
                else:
                    approval_status = 'pending'
                    suggested_fix += " [Aviso: Orçamento limite atingido; auto-regeneração requer aprovação manual]."
            else:
                approval_status = 'none'

        check_id = uuid.uuid4().hex
        now = self._now()

        result = FidelityCheckResult(
            id=check_id,
            campaign_id=campaign_id,
            slide_id=slide_id,
            version_id=version_id,
            product_id=product_id,
            asset_id=asset_id,
            score=final_score,
            threshold=threshold,
            mode=mode,
            status=status,
            passed=passed,
            dimensions=dimension_results,
            discrepancies=discrepancies,
            suggested_fix=suggested_fix,
            estimated_correction_cost=estimated_cost,
            approval_status=approval_status,
            is_estimated=True,
            created_at=now,
        )

        # Persiste no banco de dados SQLite
        with sqlite3.connect(self.database.path) as conn:
            conn.execute(
                '''INSERT INTO product_fidelity_checks (
                    id, campaign_id, slide_id, version_id, product_id, asset_id,
                    score, threshold, mode, status, checked_attributes_json,
                    discrepancies_json, suggested_fix, estimated_correction_cost,
                    approval_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    check_id, campaign_id, slide_id, version_id, product_id, asset_id,
                    final_score, threshold, mode, status,
                    json.dumps({k: v.to_dict() for k, v in dimension_results.items()}, ensure_ascii=False),
                    json.dumps([d.to_dict() for d in discrepancies], ensure_ascii=False),
                    suggested_fix, float(estimated_cost), approval_status, now,
                ),
            )

            # Atualiza versão de execução se fornecida (M06-A03)
            if version_id:
                conn.execute(
                    '''UPDATE execution_versions
                       SET fidelity_score=?, fidelity_details_json=?, fidelity_status=?
                       WHERE id=?''',
                    (
                        final_score,
                        json.dumps(result.to_dict(), ensure_ascii=False),
                        status,
                        version_id,
                    ),
                )

        return result

    def get_check(self, check_id: str) -> Optional[FidelityCheckResult]:
        with sqlite3.connect(self.database.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM product_fidelity_checks WHERE id=?', (check_id,)).fetchone()
            if not row:
                return None
            return self._row_to_result(row)

    def list_checks_for_campaign(self, campaign_id: str) -> List[FidelityCheckResult]:
        with sqlite3.connect(self.database.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                'SELECT * FROM product_fidelity_checks WHERE campaign_id=? ORDER BY created_at DESC',
                (campaign_id,),
            ).fetchall()
            return [self._row_to_result(r) for r in rows]

    def list_checks_for_slide(self, slide_id: str) -> List[FidelityCheckResult]:
        with sqlite3.connect(self.database.path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                'SELECT * FROM product_fidelity_checks WHERE slide_id=? ORDER BY created_at DESC',
                (slide_id,),
            ).fetchall()
            return [self._row_to_result(r) for r in rows]

    def approve_correction(self, check_id: str, approver: str = 'user') -> Dict[str, Any]:
        """Aprova a sugestão de correção de fidelidade e autoriza regeneração (Seção 27)."""
        with sqlite3.connect(self.database.path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM product_fidelity_checks WHERE id=?', (check_id,)).fetchone()
            if not row:
                raise ValueError('Check de fidelidade não encontrado.')
            if row['approval_status'] == 'approved':
                return {'check_id': check_id, 'status': 'already_approved'}

            conn.execute(
                "UPDATE product_fidelity_checks SET approval_status='approved' WHERE id=?",
                (check_id,),
            )
            return {
                'check_id': check_id,
                'campaign_id': row['campaign_id'],
                'slide_id': row['slide_id'],
                'suggested_fix': row['suggested_fix'],
                'estimated_cost': float(row['estimated_correction_cost']),
                'approver': approver,
                'status': 'approved',
            }

    def _row_to_result(self, row: sqlite3.Row) -> FidelityCheckResult:
        dim_data = json.loads(row['checked_attributes_json'] or '{}')
        dimensions = {
            k: FidelityDimensionResult(
                dimension=v['dimension'],
                score=float(v['score']),
                weight=float(v['weight']),
                status=v['status'],
                discrepancies=[FidelityDiscrepancy(**d) for d in v.get('discrepancies', [])],
            )
            for k, v in dim_data.items()
        }
        disc_data = json.loads(row['discrepancies_json'] or '[]')
        discrepancies = [FidelityDiscrepancy(**d) for d in disc_data]

        return FidelityCheckResult(
            id=row['id'],
            campaign_id=row['campaign_id'],
            slide_id=row['slide_id'],
            version_id=row['version_id'],
            product_id=row['product_id'],
            asset_id=row['asset_id'],
            score=float(row['score']),
            threshold=float(row['threshold']),
            mode=row['mode'],
            status=row['status'],
            passed=(row['status'] == 'passed'),
            dimensions=dimensions,
            discrepancies=discrepancies,
            suggested_fix=row['suggested_fix'],
            estimated_correction_cost=float(row['estimated_correction_cost']),
            approval_status=row['approval_status'],
            is_estimated=True,
            created_at=row['created_at'],
        )
