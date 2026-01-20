"""Alert models."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List


class AlertLevel(str, Enum):
    """Alert severity levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class Alert:
    """Alert message."""
    level: AlertLevel
    title: str
    message: str
    timestamp: datetime
    source: str = "system"
    metadata: Optional[Dict] = None
    sent: bool = False


@dataclass
class AlertConfig:
    """Alert service configuration."""
    telegram_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    email_smtp_host: Optional[str] = None
    email_smtp_port: int = 587
    email_username: Optional[str] = None
    email_password: Optional[str] = None
    email_recipients: List[str] = field(default_factory=list)
    min_level: AlertLevel = AlertLevel.WARNING
    rate_limit_seconds: int = 60
