"""Shared data shapes."""
import html
import re
from dataclasses import dataclass, field
from datetime import datetime

MAX_BODY_CHARS = 1500

_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")


def clean_text(raw: str | None, limit: int = MAX_BODY_CHARS) -> str:
    """Strip HTML tags/entities and collapse whitespace; long code dumps get cut short."""
    if not raw:
        return ""
    text = _SPACE.sub(" ", html.unescape(_TAG.sub(" ", raw))).strip()
    return text[:limit]


@dataclass
class Post:
    source: str
    external_id: str
    title: str
    body: str
    url: str
    score: int
    comments: int
    created_at: datetime
    is_answered: bool | None = None
    matched_keywords: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{self.source}:{self.external_id}"

    @property
    def engagement(self) -> int:
        return self.score + self.comments

    def to_row(self) -> dict:
        """Collector-owned columns only, so re-fetching a post never wipes its AI labels."""
        return {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "body": self.body,
            "url": self.url,
            "score": self.score,
            "comments": self.comments,
            "is_answered": self.is_answered,
            "created_at": self.created_at.isoformat(),
            "matched_keywords": sorted(set(self.matched_keywords)),
        }
