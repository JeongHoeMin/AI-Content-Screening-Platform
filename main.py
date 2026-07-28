from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


def main() -> None:
    logger.info("application_started")


if __name__ == "__main__":
    main()
