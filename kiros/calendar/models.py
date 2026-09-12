"""Modelos e contratos do Calendário Editorial Inteligente (Seções 39, 40, 41, 42)."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional


VALID_PILLARS = (
    'lancamento',
    'educativo',
    'institucional',
    'bastidores',
    'engajamento',
    'lifestyle',
)

VALID_PRIORITIES = (
    'low',
    'medium',
    'high',
    'critical',
)

VALID_CONTENT_TYPES = (
    'feed',
    'carousel',
    'stories',
    'reels',
)

VALID_ENTRY_STATUSES = (
    'draft',
    'scheduled',
    'publishing',
    'published',
    'failed',
    'cancelled',
)

SEASONAL_PHASES = (
    'warm_up',
    'consideracao',
    'conversao',
    'last_call',
    'none',
)

DATA_LAYERS = (
    'kiros',
    'setor',
    'plataforma_geral',
)


@dataclass
class CalendarPreferences:
    id: str = 'default'
    max_posts_per_week: int = 4
    min_hours_between_posts: int = 24
    preferred_days: List[str] = field(default_factory=lambda: ['seg', 'qua', 'sex', 'dom'])
    preferred_time_ranges: List[Dict[str, str]] = field(default_factory=lambda: [{'start': '18:00', 'end': '20:00'}])
    saturation_threshold_per_pillar_per_week: int = 2
    updated_at: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'max_posts_per_week': self.max_posts_per_week,
            'min_hours_between_posts': self.min_hours_between_posts,
            'preferred_days': list(self.preferred_days),
            'preferred_time_ranges': list(self.preferred_time_ranges),
            'saturation_threshold_per_pillar_per_week': self.saturation_threshold_per_pillar_per_week,
            'updated_at': self.updated_at,
        }


@dataclass
class TimeRecommendation:
    recommended_time: str
    selected_time: str
    accepted: bool
    data_basis: Dict[str, Any]
    later_performance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'recommended_time': self.recommended_time,
            'selected_time': self.selected_time,
            'accepted': self.accepted,
            'data_basis': self.data_basis,
            'later_performance': self.later_performance,
        }


@dataclass
class CalendarEntry:
    id: str
    campaign_id: Optional[str] = None
    slide_id: Optional[str] = None
    sequence_id: Optional[str] = None
    title: str = ''
    content_type: str = 'feed'
    pillar: str = 'institucional'
    priority: str = 'medium'
    seasonal_tag: Optional[str] = None
    phase: str = 'none'
    status: str = 'draft'
    scheduled_for: Optional[str] = None
    recommended_time: Optional[str] = None
    selected_time: Optional[str] = None
    time_accepted: bool = True
    data_basis: Dict[str, Any] = field(default_factory=dict)
    later_performance: Dict[str, Any] = field(default_factory=dict)
    format_specs: Dict[str, Any] = field(default_factory=dict)
    notes: str = ''
    created_at: str = ''
    updated_at: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'campaign_id': self.campaign_id,
            'slide_id': self.slide_id,
            'sequence_id': self.sequence_id,
            'title': self.title,
            'content_type': self.content_type,
            'pillar': self.pillar,
            'priority': self.priority,
            'seasonal_tag': self.seasonal_tag,
            'phase': self.phase,
            'status': self.status,
            'scheduled_for': self.scheduled_for,
            'recommended_time': self.recommended_time,
            'selected_time': self.selected_time,
            'time_accepted': self.time_accepted,
            'data_basis': self.data_basis,
            'later_performance': self.later_performance,
            'format_specs': self.format_specs,
            'notes': self.notes,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

