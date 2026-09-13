"""Utilidades canônicas de Fuso Horário e Formatação de Data/Hora (São Paulo, Brasil - 24h).

Garante que todas as datas e horários do estúdio KIROS sigam:
- Fuso Horário: America/Sao_Paulo (UTC-03:00 / Horário de Brasília)
- Formato de Horas: 24 horas (00:00 a 23:59)
- Formato de Data Brasileiro: DD/MM/YYYY
"""
from datetime import datetime, date, time, timezone
from typing import Any, Optional, Union
from zoneinfo import ZoneInfo

# Fuso horário padrão canônico da marca KIROS (Sorocaba/SP, Brasil)
SAO_PAULO_TZ = ZoneInfo('America/Sao_Paulo')

MESES_PT = [
    'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
    'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
]


def now_sp() -> datetime:
    """Retorna o datetime atual no fuso de São Paulo (UTC-3)."""
    return datetime.now(SAO_PAULO_TZ)


def now_sp_iso() -> str:
    """Retorna o timestamp ISO 8601 atual com timezone de São Paulo."""
    return now_sp().isoformat()


def to_sp(val: Any) -> Optional[datetime]:
    """Converte datetime, string ISO ou timestamp para datetime em America/Sao_Paulo."""
    if val is None or val == '':
        return None
    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(val, tz=SAO_PAULO_TZ)
    if isinstance(val, datetime):
        if val.tzinfo is not None:
            return val.astimezone(SAO_PAULO_TZ)
        return val.replace(tzinfo=SAO_PAULO_TZ)
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return None
        # Normaliza 'Z' para '+00:00' para compatibilidade ISO
        cleaned = val.replace('Z', '+00:00')
        try:
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is not None:
                return dt.astimezone(SAO_PAULO_TZ)
            return dt.replace(tzinfo=SAO_PAULO_TZ)
        except ValueError:
            return None
    return None


def format_sp(val: Any, fmt: str = '%d/%m/%Y %H:%M') -> str:
    """Formata valor para string em fuso de São Paulo no formato 24h."""
    dt = to_sp(val)
    if not dt:
        return '—'
    return dt.strftime(fmt)


def format_sp_date(val: Any) -> str:
    """Retorna apenas a data formatada: DD/MM/YYYY."""
    return format_sp(val, fmt='%d/%m/%Y')


def format_sp_time(val: Any) -> str:
    """Retorna apenas o horário em 24h: HH:MM."""
    return format_sp(val, fmt='%H:%M')


def format_sp_display(val: Any) -> str:
    """Retorna data e hora legível em 24h: DD/MM/YYYY às HH:MM."""
    dt = to_sp(val)
    if not dt:
        return 'A definir'
    return f"{dt.strftime('%d/%m/%Y às %H:%M')}"


def format_sp_friendly(val: Any) -> str:
    """Retorna formato amigável extenso: 13 de setembro de 2026 às 19:30."""
    dt = to_sp(val)
    if not dt:
        return 'A definir'
    mes = MESES_PT[dt.month - 1]
    return f"{dt.day} de {mes} de {dt.year} às {dt.strftime('%H:%M')}"


def format_sp_day_month(val: Any) -> str:
    """Retorna formato conciso: 13 de setembro de 2026."""
    dt = to_sp(val)
    if not dt:
        return ''
    mes = MESES_PT[dt.month - 1]
    return f"{dt.day} de {mes} de {dt.year}"


def format_sp_input(val: Any) -> str:
    """Formata valor para o atributo value de inputs <input type="datetime-local"> (YYYY-MM-DDTHH:MM)."""
    dt = to_sp(val)
    if not dt:
        dt = now_sp()
    return dt.strftime('%Y-%m-%dT%H:%M')


def ensure_sp_iso(val: Any) -> str:
    """Garante que a string resultante seja uma data ISO 8601 timezone-aware no fuso de São Paulo (-03:00)."""
    dt = to_sp(val)
    if not dt:
        dt = now_sp()
    return dt.isoformat()


def normalize_input_sp_iso(val: Any) -> str:
    """Se a data não tiver fuso horário (ex: input datetime-local), anexa o fuso de São Paulo (-03:00). Se já possuir timezone explícito, preserva."""
    if not val:
        return now_sp_iso()
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=SAO_PAULO_TZ).isoformat()
        return val.isoformat()
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return now_sp_iso()
        try:
            dt = datetime.fromisoformat(val.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                return dt.replace(tzinfo=SAO_PAULO_TZ).isoformat()
            return val
        except ValueError:
            return val
    return ensure_sp_iso(val)
