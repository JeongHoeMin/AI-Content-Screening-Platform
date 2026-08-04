from __future__ import annotations

from enum import Enum


class CommunityType(str, Enum):
    """Supported community sources."""

    REDDIT = "reddit"
    DCINSIDE = "dcinside"
    RULIWEB = "ruliweb"
    MOCK = "mock"
    NAVER_NEWS = "naver_news"
    DART = "dart"
    IR_RSS = "ir_rss"
