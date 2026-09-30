"""Structured file logging for search failures, engine skips, and seed fallbacks."""

import logging
from pathlib import Path

_DEFAULT_LOG = Path("leadlens_enrichment.log")
_logger: logging.Logger | None = None


def setup_logger(log_path: str | Path | None = None) -> logging.Logger:
    """Configure and return the module logger (idempotent)."""
    global _logger
    if _logger is not None:
        return _logger

    path = Path(log_path) if log_path else _DEFAULT_LOG
    path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("leadlens")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    logger.addHandler(fh)

    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    if _logger is None:
        return setup_logger()
    return _logger


def log_search_engine_failure(engine: str, query: str, reason: str, attempt: int | None = None) -> None:
    msg = f"search_engine={engine} query={query!r} reason={reason}"
    if attempt is not None:
        msg = f"attempt={attempt} {msg}"
    get_logger().warning(msg)


def log_search_engine_skip(engine: str, reason: str) -> None:
    get_logger().warning(f"search_engine_skip engine={engine} reason={reason}")


def log_search_engine_ok(engine: str, query: str, result_count: int) -> None:
    get_logger().info(f"search_engine_ok engine={engine} query={query!r} results={result_count}")


def log_seed_fallback(entity_name: str, field: str) -> None:
    get_logger().info(f"seed_fallback entity={entity_name!r} field={field}")
