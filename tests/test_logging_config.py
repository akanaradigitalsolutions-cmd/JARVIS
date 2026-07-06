import logging

from jarvis.core.config import settings
from jarvis.core.logging_config import get_logger, setup_logging


def test_get_logger_uses_jarvis_namespace():
    log = get_logger("something")
    assert log.name == "jarvis.something"


def test_setup_logging_creates_log_file_and_is_idempotent():
    setup_logging()
    setup_logging()  # should not add duplicate handlers
    root = logging.getLogger("jarvis")
    assert (settings.jarvis_home / "logs" / "jarvis.log").exists()
    assert len(root.handlers) == len({id(h) for h in root.handlers})


def test_logger_actually_writes_to_the_log_file():
    log = get_logger("test-writer")
    log.info("a distinctive log line for the test")
    log_path = settings.jarvis_home / "logs" / "jarvis.log"
    assert "a distinctive log line for the test" in log_path.read_text()
