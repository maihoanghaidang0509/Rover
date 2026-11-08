"""Central logging — mỗi dòng log xuống hàng riêng, không chéo/TAB dài."""

from __future__ import annotations

import atexit
import logging
import queue
import sys
import threading
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from pathlib import Path

_STDIO_LOCK = threading.RLock()
_listener: QueueListener | None = None


def _sanitize_log_text(text: str) -> str:
    """Một dòng duy nhất — bỏ \\r, TAB, newline lạ."""
    return " ".join(text.replace("\r", " ").split())


def _emit_console_line(text: str) -> None:
    with _STDIO_LOCK:
        stream = sys.__stderr__
        line = _sanitize_log_text(text)
        if line:
            stream.write(line + "\n")
            stream.flush()


class LineNormalizedWriter:
    """Gom mọi ghi stdout/stderr thành từng dòng (xử lý \\r và thiếu \\n)."""

    def __init__(self, stream):
        self._stream = stream
        self._buffer = ""

    def write(self, s: str) -> int:
        if not s:
            return 0
        with _STDIO_LOCK:
            self._buffer += s.replace("\r\n", "\n").replace("\r", "\n")
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                line = _sanitize_log_text(line)
                if line:
                    self._stream.write(line + "\n")
            return len(s)

    def flush(self) -> None:
        with _STDIO_LOCK:
            rest = _sanitize_log_text(self._buffer)
            if rest:
                self._stream.write(rest + "\n")
            self._buffer = ""
            self._stream.flush()

    def fileno(self):
        return self._stream.fileno()

    def isatty(self):
        return self._stream.isatty()


def _install_line_safe_stdio() -> None:
    if getattr(sys, "_uavlink_line_safe_stdio", False):
        return
    sys.stdout = LineNormalizedWriter(sys.__stdout__)  # type: ignore[assignment]
    sys.stderr = LineNormalizedWriter(sys.__stderr__)  # type: ignore[assignment]
    sys._uavlink_line_safe_stdio = True  # type: ignore[attr-defined]


class CleanConsoleHandler(logging.Handler):
    """Console: một dòng / record, không in traceback (traceback chỉ vào file)."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            saved_exc = record.exc_info
            record.exc_info = None
            record.exc_text = None
            _emit_console_line(self.format(record))
            if saved_exc:
                record.exc_info = saved_exc
        except Exception:
            self.handleError(record)


class CleanFileHandler(RotatingFileHandler):
    """File log — dùng formatter chuẩn (traceback nhiều dòng OK trong file)."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            super().emit(record)
        except Exception:
            self.handleError(record)


def _stop_listener() -> None:
    global _listener
    if _listener is not None:
        try:
            _listener.stop()
        except Exception:
            pass
        _listener = None


def configure_quiet_werkzeug() -> None:
    for name in ("werkzeug", "werkzeug.serving"):
        log = logging.getLogger(name)
        log.handlers.clear()
        log.propagate = True
        log.setLevel(logging.ERROR)

    try:
        import werkzeug.serving

        def _log_via_logging(log_type: str, message: str, *args) -> None:
            text = message % args if args else message
            text = _sanitize_log_text(text)
            log = logging.getLogger("werkzeug")
            if log_type == "error":
                log.error(text)
            elif log_type == "warning":
                log.warning(text)
            else:
                log.debug(text)

        werkzeug.serving._log = _log_via_logging  # type: ignore[attr-defined]
    except Exception:
        pass

    try:
        import flask.cli

        flask.cli.show_server_banner = lambda *args, **kwargs: None  # type: ignore[attr-defined]
    except Exception:
        pass

    try:
        import flask.app

        def _quiet_log_exception(self, exc):  # noqa: ARG001
            logging.getLogger("WebServer").error("[WEB] %s", exc)

        flask.app.Flask.log_exception = _quiet_log_exception  # type: ignore[method-assign]
    except Exception:
        pass


def setup_logging(level: str = "INFO", log_dir: Path | None = None) -> None:
    global _listener

    _install_line_safe_stdio()
    configure_quiet_werkzeug()

    log_dir = log_dir or Path(__file__).resolve().parent / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    _stop_listener()

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, str(level).upper(), logging.INFO))

    fmt = logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = CleanConsoleHandler()
    console.setFormatter(fmt)

    file_handler = CleanFileHandler(
        log_dir / "uavlink-edge.log",
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    log_queue: queue.Queue[logging.LogRecord] = queue.Queue(-1)
    root.addHandler(QueueHandler(log_queue))

    _listener = QueueListener(
        log_queue,
        console,
        file_handler,
        respect_handler_level=True,
    )
    _listener.daemon = True
    _listener.start()
    atexit.register(_stop_listener)
