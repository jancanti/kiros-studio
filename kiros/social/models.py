"""Modelos e contratos de Publicação no Instagram e Auditoria de Governança (Seções 41, 42, 68, 69, 70, 79)."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


INSTAGRAM_PERMISSIONS = (
    'instagram_basic',
    'instagram_content_publish',
    'pages_show_list',
    'pages_read_engagement',
)

MAX_POSTS_PER_24_HOURS = 25
MIN_SCHEDULE_AHEAD_SECONDS = 900       # 15 minutos (limite mínimo oficial da Meta)
MAX_SCHEDULE_AHEAD_SECONDS = 6480000   # 75 dias (limite máximo oficial da Meta)

SUPPORTED_MEDIA_TYPES = (
    'IMAGE',
    'CAROUSEL',
    'STORIES',
    'VIDEO',
)

SUPPORTED_ASPECT_RATIOS = {
    '1:1': {'ratio': 1.0, 'name': 'Quadrado Feed', 'min_width': 320, 'max_width': 1440},
    '4:5': {'ratio': 0.8, 'name': 'Retrato Feed', 'min_width': 320, 'max_width': 1440},
    '9:16': {'ratio': 0.5625, 'name': 'Stories Vertical', 'min_width': 540, 'max_width': 1080},
    '1.91:1': {'ratio': 1.91, 'name': 'Paisagem Feed', 'min_width': 600, 'max_width': 1440},
}

MAX_IMAGE_FILE_SIZE_BYTES = 8 * 1024 * 1024    # 8 MB
MAX_STORY_FILE_SIZE_BYTES = 4 * 1024 * 1024    # 4 MB


@dataclass
class SocialPublication:
    id: str
    calendar_entry_id: Optional[str]
    campaign_id: Optional[str]
    asset_id: str
    caption: str
    media_type: str = 'IMAGE'
    idempotency_key: str = ''
    status: str = 'pending'  # pending, publishing, published, failed
    provider: str = 'mock'
    external_container_id: Optional[str] = None
    external_post_id: Optional[str] = None
    explicit_confirmed_by: Optional[str] = None
    explicit_confirmed_at: Optional[str] = None
    audit_id: Optional[str] = None
    scheduled_publish_time: Optional[str] = None
    error_message: Optional[str] = None
    published_at: Optional[str] = None
    created_at: str = ''
    updated_at: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'calendar_entry_id': self.calendar_entry_id,
            'campaign_id': self.campaign_id,
            'asset_id': self.asset_id,
            'caption': self.caption,
            'media_type': self.media_type,
            'idempotency_key': self.idempotency_key,
            'status': self.status,
            'provider': self.provider,
            'external_container_id': self.external_container_id,
            'external_post_id': self.external_post_id,
            'explicit_confirmed_by': self.explicit_confirmed_by,
            'explicit_confirmed_at': self.explicit_confirmed_at,
            'audit_id': self.audit_id,
            'scheduled_publish_time': self.scheduled_publish_time,
            'error_message': self.error_message,
            'published_at': self.published_at,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }


@dataclass
class AccountStatus:
    id: str = 'default'
    account_id: Optional[str] = None
    username: Optional[str] = None
    account_type: str = 'business'
    connection_status: str = 'unvalidated'  # unvalidated, mock, connected, expired
    permissions: List[str] = field(default_factory=lambda: list(INSTAGRAM_PERMISSIONS))
    rate_limit_total: int = MAX_POSTS_PER_24_HOURS
    rate_limit_remaining: int = MAX_POSTS_PER_24_HOURS
    last_checked_at: Optional[str] = None
    updated_at: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'account_id': self.account_id,
            'username': self.username,
            'account_type': self.account_type,
            'connection_status': self.connection_status,
            'permissions': list(self.permissions),
            'rate_limit_total': self.rate_limit_total,
            'rate_limit_remaining': self.rate_limit_remaining,
            'last_checked_at': self.last_checked_at,
            'updated_at': self.updated_at,
        }

