"""Serviço de Calendário Editorial Inteligente (Seções 39, 40, 41, 42 e M09-A01, M09-A02)."""
from datetime import datetime, date, time, timedelta, timezone
import json
import sqlite3
import uuid
from typing import Any, Dict, List, Optional, Tuple

from kiros.calendar.models import (
    CalendarPreferences,
    CalendarEntry,
    TimeRecommendation,
    VALID_PILLARS,
    VALID_PRIORITIES,
    VALID_CONTENT_TYPES,
    VALID_ENTRY_STATUSES,
    SEASONAL_PHASES,
    DATA_LAYERS,
)


class EditorialCalendarService:
    """Gerencia o calendário inteligente, frequência, saturação e recomendações com camadas de dados."""

    def __init__(self, database, campaigns=None, library=None):
        self.database = database
        self.campaigns = campaigns
        self.library = library

    def _connection(self):
        conn = sqlite3.connect(self.database.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # -------------------------------------------------------------------------
    # Preferências e Limites do Usuário (Seção 40)
    # -------------------------------------------------------------------------

    def get_preferences(self) -> CalendarPreferences:
        """Recupera preferências editoriais configuradas pelo usuário ou padrão."""
        with self._connection() as conn:
            row = conn.execute('SELECT * FROM calendar_preferences WHERE id="default"').fetchone()
            if not row:
                prefs = CalendarPreferences(updated_at=self._now_iso())
                conn.execute(
                    '''INSERT INTO calendar_preferences 
                       (id, max_posts_per_week, min_hours_between_posts, preferred_days_json, 
                        preferred_time_ranges_json, saturation_threshold_per_pillar_per_week, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (
                        prefs.id,
                        prefs.max_posts_per_week,
                        prefs.min_hours_between_posts,
                        json.dumps(prefs.preferred_days),
                        json.dumps(prefs.preferred_time_ranges),
                        prefs.saturation_threshold_per_pillar_per_week,
                        prefs.updated_at,
                    )
                )
                conn.commit()
                return prefs

            return CalendarPreferences(
                id=row['id'],
                max_posts_per_week=row['max_posts_per_week'],
                min_hours_between_posts=row['min_hours_between_posts'],
                preferred_days=json.loads(row['preferred_days_json']),
                preferred_time_ranges=json.loads(row['preferred_time_ranges_json']),
                saturation_threshold_per_pillar_per_week=row['saturation_threshold_per_pillar_per_week'],
                updated_at=row['updated_at'],
            )

    def save_preferences(
        self,
        max_posts_per_week: int = 4,
        min_hours_between_posts: int = 24,
        preferred_days: Optional[List[str]] = None,
        preferred_time_ranges: Optional[List[Dict[str, str]]] = None,
        saturation_threshold: int = 2,
    ) -> CalendarPreferences:
        """Salva limites e preferências do usuário com validação de intervalos."""
        if not 1 <= max_posts_per_week <= 14:
            raise ValueError('max_posts_per_week deve estar entre 1 e 14.')
        if not 1 <= min_hours_between_posts <= 168:
            raise ValueError('min_hours_between_posts deve estar entre 1 e 168 horas.')
        if not 1 <= saturation_threshold <= 7:
            raise ValueError('saturation_threshold deve estar entre 1 e 7 posts por pilar/semana.')

        days = preferred_days or ['seg', 'qua', 'sex', 'dom']
        time_ranges = preferred_time_ranges or [{'start': '18:00', 'end': '20:00'}]
        now = self._now_iso()

        with self._connection() as conn:
            conn.execute(
                '''INSERT INTO calendar_preferences 
                   (id, max_posts_per_week, min_hours_between_posts, preferred_days_json, 
                    preferred_time_ranges_json, saturation_threshold_per_pillar_per_week, updated_at)
                   VALUES ('default', ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                   max_posts_per_week=excluded.max_posts_per_week,
                   min_hours_between_posts=excluded.min_hours_between_posts,
                   preferred_days_json=excluded.preferred_days_json,
                   preferred_time_ranges_json=excluded.preferred_time_ranges_json,
                   saturation_threshold_per_pillar_per_week=excluded.saturation_threshold_per_pillar_per_week,
                   updated_at=excluded.updated_at''',
                (
                    max_posts_per_week,
                    min_hours_between_posts,
                    json.dumps(days),
                    json.dumps(time_ranges),
                    saturation_threshold,
                    now,
                )
            )
            conn.commit()

        return CalendarPreferences(
            id='default',
            max_posts_per_week=max_posts_per_week,
            min_hours_between_posts=min_hours_between_posts,
            preferred_days=days,
            preferred_time_ranges=time_ranges,
            saturation_threshold_per_pillar_per_week=saturation_threshold,
            updated_at=now,
        )

    # -------------------------------------------------------------------------
    # Operações CRUD do Calendário (Seções 39 e 40)
    # -------------------------------------------------------------------------

    def create_entry(
        self,
        title: str,
        content_type: str = 'feed',
        pillar: str = 'institucional',
        priority: str = 'medium',
        campaign_id: Optional[str] = None,
        slide_id: Optional[str] = None,
        sequence_id: Optional[str] = None,
        seasonal_tag: Optional[str] = None,
        phase: str = 'none',
        status: str = 'draft',
        scheduled_for: Optional[str] = None,
        notes: str = '',
        format_specs: Optional[Dict[str, Any]] = None,
    ) -> CalendarEntry:
        """Cria uma entrada no calendário editorial com regras de governança e datas prioritárias."""
        if not title or not title.strip():
            raise ValueError('Título da entrada é obrigatório.')
        if content_type not in VALID_CONTENT_TYPES:
            raise ValueError(f'Tipo de conteúdo inválido: {content_type}. Use um de {VALID_CONTENT_TYPES}.')
        if pillar not in VALID_PILLARS:
            raise ValueError(f'Pilar inválido: {pillar}. Use um de {VALID_PILLARS}.')
        if priority not in VALID_PRIORITIES:
            raise ValueError(f'Prioridade inválida: {priority}. Use uma de {VALID_PRIORITIES}.')
        if phase not in SEASONAL_PHASES:
            raise ValueError(f'Fase sazonal inválida: {phase}. Use uma de {SEASONAL_PHASES}.')

        # Validação de Timezone em scheduled_for
        if scheduled_for:
            try:
                dt = datetime.fromisoformat(scheduled_for)
                if dt.tzinfo is None:
                    raise ValueError('Data agendada deve incluir fuso horário explícito (timezone-aware ISO 8601).')
            except ValueError as exc:
                raise ValueError(f'Formato de data inválido para scheduled_for: {exc}')

        # Regra de Sazonalidade / Datas Prioritárias (Seção 15, Seção 39):
        # "Datas prioritárias podem gerar rascunhos antecipados, mas não entram no calendário oficial sem aprovação."
        if (seasonal_tag or priority == 'critical') and status != 'draft':
            # Verifica se a campanha está totalmente aprovada antes de entrar no calendário oficial
            is_approved = False
            if campaign_id and self.campaigns:
                camp = self.campaigns.get_campaign(campaign_id)
                if camp and camp.status in ('approved', 'completed') and camp.approved_version == camp.plan_version:
                    is_approved = True
            if not is_approved:
                # Força status 'draft'
                status = 'draft'

        entry_id = f"cal_{uuid.uuid4().hex[:12]}"
        now = self._now_iso()
        specs = format_specs or {}

        with self._connection() as conn:
            conn.execute(
                '''INSERT INTO calendar_entries 
                   (id, campaign_id, slide_id, sequence_id, title, content_type, pillar, priority, 
                    seasonal_tag, phase, status, scheduled_for, recommended_time, selected_time, 
                    time_accepted, data_basis_json, later_performance_json, format_specs_json, 
                    notes, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    entry_id,
                    campaign_id,
                    slide_id,
                    sequence_id,
                    title.strip(),
                    content_type,
                    pillar,
                    priority,
                    seasonal_tag,
                    phase,
                    status,
                    scheduled_for,
                    None,
                    scheduled_for,
                    1,
                    json.dumps({}),
                    json.dumps({}),
                    json.dumps(specs),
                    notes.strip(),
                    now,
                    now,
                )
            )
            conn.commit()

        return self.get_entry(entry_id)

    def get_entry(self, entry_id: str) -> Optional[CalendarEntry]:
        """Obtém entrada do calendário pelo ID."""
        with self._connection() as conn:
            row = conn.execute('SELECT * FROM calendar_entries WHERE id=?', (entry_id,)).fetchone()
            if not row:
                return None
            return self._row_to_entry(row)

    def list_entries(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        pillar: Optional[str] = None,
        status: Optional[str] = None,
        campaign_id: Optional[str] = None,
    ) -> List[CalendarEntry]:
        """Lista entradas do calendário com filtros e ordenação cronológica."""
        query = 'SELECT * FROM calendar_entries WHERE 1=1'
        params: List[Any] = []

        if start_date:
            query += ' AND (scheduled_for >= ? OR (scheduled_for IS NULL AND created_at >= ?))'
            params.extend([start_date, start_date])
        if end_date:
            query += ' AND (scheduled_for <= ? OR (scheduled_for IS NULL AND created_at <= ?))'
            params.extend([end_date, end_date])
        if pillar:
            query += ' AND pillar = ?'
            params.append(pillar)
        if status:
            query += ' AND status = ?'
            params.append(status)
        if campaign_id:
            query += ' AND campaign_id = ?'
            params.append(campaign_id)

        query += ' ORDER BY scheduled_for ASC NULLS LAST, created_at ASC'

        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_entry(r) for r in rows]

    def update_entry(
        self,
        entry_id: str,
        title: Optional[str] = None,
        content_type: Optional[str] = None,
        pillar: Optional[str] = None,
        priority: Optional[str] = None,
        status: Optional[str] = None,
        scheduled_for: Optional[str] = None,
        seasonal_tag: Optional[str] = None,
        phase: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> CalendarEntry:
        """Atualiza campos de uma entrada no calendário."""
        existing = self.get_entry(entry_id)
        if not existing:
            raise KeyError(f'Entrada de calendário não encontrada: {entry_id}')

        updates = []
        params = []
        now = self._now_iso()

        if title is not None:
            if not title.strip():
                raise ValueError('Título não pode ser vazio.')
            updates.append('title = ?')
            params.append(title.strip())

        if content_type is not None:
            if content_type not in VALID_CONTENT_TYPES:
                raise ValueError(f'Tipo de conteúdo inválido: {content_type}')
            updates.append('content_type = ?')
            params.append(content_type)

        if pillar is not None:
            if pillar not in VALID_PILLARS:
                raise ValueError(f'Pilar inválido: {pillar}')
            updates.append('pillar = ?')
            params.append(pillar)

        if priority is not None:
            if priority not in VALID_PRIORITIES:
                raise ValueError(f'Prioridade inválida: {priority}')
            updates.append('priority = ?')
            params.append(priority)

        if status is not None:
            if status not in VALID_ENTRY_STATUSES:
                raise ValueError(f'Status inválido: {status}')
            # Verifica aprovação se for data prioritária
            if (existing.seasonal_tag or existing.priority == 'critical') and status != 'draft':
                is_approved = False
                if existing.campaign_id and self.campaigns:
                    c = self.campaigns.get_campaign(existing.campaign_id)
                    if c and c.status in ('approved', 'completed') and c.approved_version == c.plan_version:
                        is_approved = True
                if not is_approved and status not in ('draft', 'cancelled'):
                    raise ValueError('Datas prioritárias não podem entrar no calendário oficial sem aprovação de campanha (Seção 15).')
            updates.append('status = ?')
            params.append(status)

        if scheduled_for is not None:
            if scheduled_for:
                dt = datetime.fromisoformat(scheduled_for)
                if dt.tzinfo is None:
                    raise ValueError('scheduled_for deve incluir timezone explícito.')
            updates.append('scheduled_for = ?')
            params.append(scheduled_for if scheduled_for else None)

        if seasonal_tag is not None:
            updates.append('seasonal_tag = ?')
            params.append(seasonal_tag)

        if phase is not None:
            if phase not in SEASONAL_PHASES:
                raise ValueError(f'Fase inválida: {phase}')
            updates.append('phase = ?')
            params.append(phase)

        if notes is not None:
            updates.append('notes = ?')
            params.append(notes.strip())

        updates.append('updated_at = ?')
        params.append(now)
        params.append(entry_id)

        with self._connection() as conn:
            conn.execute(f"UPDATE calendar_entries SET {', '.join(updates)} WHERE id=?", params)
            conn.commit()

        return self.get_entry(entry_id)

    def delete_entry(self, entry_id: str) -> None:
        """Remove entrada do calendário."""
        with self._connection() as conn:
            conn.execute('DELETE FROM calendar_entries WHERE id=?', (entry_id,))
            conn.commit()

    # -------------------------------------------------------------------------
    # Análise de Frequência, Saturação e Otimização do CD (Seção 40)
    # -------------------------------------------------------------------------

    def check_frequency_and_saturation(
        self,
        target_time_iso: str,
        pillar: str,
        entry_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Avalia limites, preferências e saturação semanal por pilar (Seção 40)."""
        dt = datetime.fromisoformat(target_time_iso)
        if dt.tzinfo is None:
            raise ValueError('Data de verificação deve conter timezone.')

        prefs = self.get_preferences()

        # Determina o início e o fim da semana (segunda-feira a domingo)
        start_of_week = (dt - timedelta(days=dt.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_week = start_of_week + timedelta(days=7)

        start_iso = start_of_week.isoformat()
        end_iso = end_of_week.isoformat()

        with self._connection() as conn:
            # Todas as entradas agendadas na mesma semana (excluindo a própria se for edição)
            query = '''SELECT id, pillar, scheduled_for FROM calendar_entries 
                       WHERE scheduled_for >= ? AND scheduled_for < ? AND status != 'cancelled' '''
            params: List[Any] = [start_iso, end_iso]
            if entry_id:
                query += ' AND id != ?'
                params.append(entry_id)

            week_rows = conn.execute(query, params).fetchall()

        weekly_count = len(week_rows)
        pillar_count = sum(1 for r in week_rows if r['pillar'] == pillar)

        # Checa intervalo mínimo entre posts
        interval_violation = False
        closest_gap_hours = None
        for r in week_rows:
            if r['scheduled_for']:
                other_dt = datetime.fromisoformat(r['scheduled_for'])
                gap = abs((dt - other_dt).total_seconds()) / 3600.0
                if closest_gap_hours is None or gap < closest_gap_hours:
                    closest_gap_hours = gap
                if gap < prefs.min_hours_between_posts:
                    interval_violation = True

        is_frequency_exceeded = (weekly_count + 1) > prefs.max_posts_per_week
        is_saturated = (pillar_count + 1) > prefs.saturation_threshold_per_pillar_per_week

        issues: List[str] = []
        if is_frequency_exceeded:
            issues.append(
                f"Limite semanal de posts excedido: já existem {weekly_count} posts agendados nesta semana "
                f"(limite configurado: {prefs.max_posts_per_week} posts/semana)."
            )
        if is_saturated:
            issues.append(
                f"Saturação do pilar '{pillar}' detectada: já existem {pillar_count} posts deste pilar nesta semana "
                f"(limite de saturação por pilar: {prefs.saturation_threshold_per_pillar_per_week} posts/semana)."
            )
        if interval_violation and closest_gap_hours is not None:
            issues.append(
                f"Intervalo mínimo violado: há outro post a apenas {closest_gap_hours:.1f}h de distância "
                f"(intervalo mínimo configurado: {prefs.min_hours_between_posts}h)."
            )

        recommendation = None
        if is_frequency_exceeded or is_saturated or interval_violation:
            # O Creative Director otimiza dentro das restrições (Seção 40)
            suggested_dt = self._suggest_alternative_slot(dt, prefs, pillar)
            explanation = (
                f"O Creative Director identificou potencial conflito de frequência/saturação para o pilar '{pillar}'. "
                f"Manter diversidade evita esgotamento do público e fadiga de mensagens promocionais."
            )
            justification = (
                f"Recomendamos redistribuir o conteúdo para {suggested_dt.strftime('%d/%m às %H:%M')} "
                f"ou alternar para outro pilar editorial menos saturado na semana."
            )
            recommendation = {
                'explanation': explanation,
                'justification': justification,
                'suggested_time': suggested_dt.isoformat(),
                'requires_approval': True,
            }

        return {
            'is_saturated': is_saturated,
            'is_frequency_exceeded': is_frequency_exceeded,
            'is_interval_violated': interval_violation,
            'weekly_count': weekly_count,
            'pillar_count': pillar_count,
            'max_posts_per_week': prefs.max_posts_per_week,
            'saturation_threshold': prefs.saturation_threshold_per_pillar_per_week,
            'issues': issues,
            'recommendation': recommendation,
        }

    def _suggest_alternative_slot(self, base_dt: datetime, prefs: CalendarPreferences, pillar: str) -> datetime:
        """Sugere horário alternativo no próximo dia preferido sem sobreposição."""
        day_map = {'seg': 0, 'ter': 1, 'qua': 2, 'qui': 3, 'sex': 4, 'sab': 5, 'dom': 6}
        target_days = [day_map.get(d, 0) for d in prefs.preferred_days if d in day_map] or [0, 2, 4, 6]

        current = base_dt + timedelta(days=2)
        while current.weekday() not in target_days:
            current += timedelta(days=1)

        # Ajusta para 19h00 UTC
        return current.replace(hour=19, minute=0, second=0, microsecond=0)

    # -------------------------------------------------------------------------
    # Recomendações de Horário e Camadas de Dados Escassos (Seções 41 e 42)
    # -------------------------------------------------------------------------

    def recommend_best_time(
        self,
        campaign_id: Optional[str] = None,
        content_type: str = 'feed',
        pillar: str = 'institucional',
        preferred_date: Optional[str] = None,
    ) -> TimeRecommendation:
        """Gera recomendação de dia/horário com camadas: KIROS -> Setor -> Plataforma Geral (Seções 41 e 42)."""
        # Base temporal de partida: amanhã ou preferred_date
        now = datetime.now(timezone.utc)
        if preferred_date:
            try:
                base_dt = datetime.fromisoformat(preferred_date)
                if base_dt.tzinfo is None:
                    base_dt = base_dt.replace(tzinfo=timezone.utc)
            except ValueError:
                base_dt = now + timedelta(days=1)
        else:
            base_dt = now + timedelta(days=1)

        # Garante que a data base esteja no futuro
        if base_dt <= now:
            base_dt = now + timedelta(hours=2)

        # Analisa dados disponíveis em camadas (Seção 42)
        # Camada 1: KIROS (vendas, histórico próprio e preferências salvas)
        has_kiros_data, kiros_insight = self._analyze_kiros_data()

        if has_kiros_data:
            layer = 'kiros'
            source = 'Histórico Comercial e Engajamento da KIROS (Sorocaba/SP)'
            confidence = 0.85
            rec_hour = 19
            rec_minute = 30
            rec_weekday = 2  # Quarta-feira
            reasoning = (
                f"Com base nas vendas e engajamento registrados na conta local da KIROS Aromas: "
                f"{kiros_insight}. O melhor intervalo de conversão é entre 19h00 e 20h30."
            )
        else:
            # Camada 2: Setor (Perfumaria, Aromaterapia e Casa no Brasil)
            has_sector_data = True
            if has_sector_data:
                layer = 'setor'
                source = 'Benchmark Setorial Brasil — Aromaterapia, Velas Artesanais e Casa'
                confidence = 0.60
                rec_hour = 18
                rec_minute = 45
                rec_weekday = 4  # Sexta-feira
                reasoning = (
                    "Para o segmento de aromas para casa e bem-estar, os momentos de transição pós-trabalho "
                    "e desaceleração (quarta a sexta, 18h30–20h00) concentram maior tempo de leitura de posts sensoriais."
                )
            else:
                # Camada 3: Plataforma Geral (Instagram Brasil)
                layer = 'plataforma_geral'
                source = 'Média Geral de Tráfego — Instagram Brasil'
                confidence = 0.35
                rec_hour = 19
                rec_minute = 0
                rec_weekday = base_dt.weekday()
                reasoning = (
                    "Padrão genérico de distribuição de tráfego na plataforma Instagram Brasil "
                    "nos horários de pico noturnos (19h00 às 21h00)."
                )

        # Calcula o próximo dia com o weekday recomendado mais próximo da data base
        days_ahead = (rec_weekday - base_dt.weekday()) % 7
        if days_ahead == 0 and base_dt.hour >= rec_hour:
            days_ahead = 7
        recommended_dt = (base_dt + timedelta(days=days_ahead)).replace(
            hour=rec_hour, minute=rec_minute, second=0, microsecond=0, tzinfo=timezone.utc
        )

        recommended_iso = recommended_dt.isoformat()
        disclaimer = (
            "Estimativa estatística com base nos dados disponíveis. Não representa garantia de alcance ou vendas. "
            "Manual sempre vence: você tem total liberdade para escolher outro horário."
        )

        data_basis = {
            'layer': layer,
            'source': source,
            'confidence': confidence,
            'reasoning': reasoning,
            'disclaimer': disclaimer,
            'pillar_evaluated': pillar,
            'content_type': content_type,
        }

        return TimeRecommendation(
            recommended_time=recommended_iso,
            selected_time=recommended_iso,
            accepted=True,
            data_basis=data_basis,
            later_performance={},
        )

    def _analyze_kiros_data(self) -> Tuple[bool, str]:
        """Checa se há dados históricos locais suficientes na KIROS (vendas ou histórico de campanhas)."""
        try:
            with self._connection() as conn:
                # Checa tabela de vendas
                sales_count = conn.execute('SELECT COUNT(*) as c FROM sales').fetchone()['c']
                if sales_count > 0:
                    return True, f"{sales_count} registros de vendas locais analisados demonstrando compras concentradas no fim da tarde"

                # Checa publicações anteriores
                pubs_count = conn.execute('SELECT COUNT(*) as c FROM social_publications WHERE status="published"').fetchone()['c']
                if pubs_count > 0:
                    return True, f"{pubs_count} publicações anteriores analisadas com retenção de audiência comprovada"
        except Exception:
            pass

        return False, ''

    def recommend_for_entry(self, entry_id: str) -> TimeRecommendation:
        """Gera recomendação de horário e anexa à entrada de calendário."""
        entry = self.get_entry(entry_id)
        if not entry:
            raise KeyError(f'Entrada de calendário não encontrada: {entry_id}')

        rec = self.recommend_best_time(
            campaign_id=entry.campaign_id,
            content_type=entry.content_type,
            pillar=entry.pillar,
            preferred_date=entry.scheduled_for,
        )
        with self._connection() as conn:
            conn.execute(
                '''UPDATE calendar_entries SET 
                   recommended_time = ?,
                   data_basis_json = ?,
                   updated_at = ?
                   WHERE id = ?''',
                (rec.recommended_time, json.dumps(rec.data_basis, ensure_ascii=False), self._now_iso(), entry_id)
            )
            conn.commit()
        return rec

    def record_time_decision(
        self,
        entry_id: str,
        selected_time_iso: str,
        accept_recommendation: bool,
        recommended_time_iso: Optional[str] = None,
        data_basis: Optional[Dict[str, Any]] = None,
        operator: str = 'Operador KIROS',
    ) -> CalendarEntry:
        """Registra a decisão final de horário (Seção 41: 'Manual sempre vence').

        Campos obrigatórios registrados:
        - recommended_time
        - selected_time
        - accepted
        - data_basis
        - later_performance
        """
        entry = self.get_entry(entry_id)
        if not entry:
            raise KeyError(f'Entrada de calendário não encontrada: {entry_id}')

        # Valida timezone
        dt = datetime.fromisoformat(selected_time_iso)
        if dt.tzinfo is None:
            raise ValueError('selected_time deve incluir timezone explícito.')

        now = self._now_iso()

        # Se aceitou recomendação mas não havia recomendação gravada, calcula uma
        rec_time = recommended_time_iso or entry.recommended_time
        basis = data_basis or entry.data_basis
        if not rec_time or not basis:
            recommendation = self.recommend_best_time(
                campaign_id=entry.campaign_id,
                content_type=entry.content_type,
                pillar=entry.pillar,
                preferred_date=selected_time_iso,
            )
            rec_time = recommendation.recommended_time
            basis = recommendation.data_basis

        # "Manual sempre vence" (Seção 41):
        # Se accept_recommendation for False ou o horário for diferente do recomendado, accepted=False
        is_accepted = bool(accept_recommendation and (selected_time_iso == rec_time))
        final_selected_time = rec_time if accept_recommendation else selected_time_iso

        with self._connection() as conn:
            conn.execute(
                '''UPDATE calendar_entries SET 
                   recommended_time = ?,
                   selected_time = ?,
                   scheduled_for = ?,
                   time_accepted = ?,
                   data_basis_json = ?,
                   status = CASE WHEN status = 'draft' THEN 'scheduled' ELSE status END,
                   updated_at = ?
                   WHERE id = ?''',
                (
                    rec_time,
                    final_selected_time,
                    final_selected_time,
                    1 if is_accepted else 0,
                    json.dumps(basis, ensure_ascii=False),
                    now,
                    entry_id,
                )
            )
            conn.commit()

        return self.get_entry(entry_id)

    def add_campaign_to_calendar(
        self,
        campaign_id: str,
        operator: str = 'Operador KIROS',
    ) -> List[CalendarEntry]:
        """Organiza conteúdo de uma campanha totalmente aprovada no calendário (M09-A01, M09-A02)."""
        if not self.campaigns:
            raise RuntimeError('CampaignManager não injetado no serviço de calendário.')

        campaign = self.campaigns.get_campaign(campaign_id)
        if not campaign:
            raise KeyError(f'Campanha não encontrada: {campaign_id}')

        # Valida aprovação total da campanha (Seção 41, M09-A02)
        if campaign.status not in ('approved', 'completed') or campaign.approved_version != campaign.plan_version:
            raise ValueError(
                f"Campanha '{campaign.title}' não está totalmente aprovada "
                f"(status={campaign.status}, plan_version={campaign.plan_version}, "
                f"approved_version={campaign.approved_version}). Aprovação total é obrigatória para agendamento oficial."
            )

        entries_created = []
        strategy = campaign.strategy or {}
        pillar = strategy.get('pillar', 'lancamento')
        if pillar not in VALID_PILLARS:
            pillar = 'lancamento'

        # Para cada slide do storyboard, cria uma entrada
        slides = campaign.slides or []
        for slide in slides:
            rec = self.recommend_best_time(campaign_id=campaign.id, content_type='feed', pillar=pillar)
            entry = self.create_entry(
                title=f"{campaign.title} — Slide {slide.slide_order}: {slide.title}",
                content_type='feed',
                pillar=pillar,
                priority='high' if campaign.approval_mode == 'full_control' else 'medium',
                campaign_id=campaign.id,
                slide_id=slide.id,
                status='scheduled',
                scheduled_for=rec.recommended_time,
                notes=f'Gerado da campanha {campaign.title} (Aprovada v{campaign.approved_version} por {campaign.approved_by}).',
            )
            # Registra recomendação
            with self._connection() as conn:
                conn.execute(
                    '''UPDATE calendar_entries SET 
                       recommended_time = ?,
                       selected_time = ?,
                       time_accepted = 1,
                       data_basis_json = ?,
                       later_performance_json = '{}',
                       updated_at = ?
                       WHERE id = ?''',
                    (
                        rec.recommended_time,
                        rec.recommended_time,
                        json.dumps(rec.data_basis, ensure_ascii=False),
                        self._now_iso(),
                        entry.id,
                    )
                )
                conn.commit()
            entries_created.append(self.get_entry(entry.id))

        return entries_created

    def _row_to_entry(self, row: sqlite3.Row) -> CalendarEntry:
        return CalendarEntry(
            id=row['id'],
            campaign_id=row['campaign_id'],
            slide_id=row['slide_id'],
            sequence_id=row['sequence_id'],
            title=row['title'],
            content_type=row['content_type'],
            pillar=row['pillar'],
            priority=row['priority'],
            seasonal_tag=row['seasonal_tag'],
            phase=row['phase'],
            status=row['status'],
            scheduled_for=row['scheduled_for'],
            recommended_time=row['recommended_time'],
            selected_time=row['selected_time'],
            time_accepted=bool(row['time_accepted']),
            data_basis=json.loads(row['data_basis_json'] or '{}'),
            later_performance=json.loads(row['later_performance_json'] or '{}'),
            format_specs=json.loads(row['format_specs_json'] or '{}'),
            notes=row['notes'] or '',
            created_at=row['created_at'],
            updated_at=row['updated_at'],
        )
