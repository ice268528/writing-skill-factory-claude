#!/usr/bin/env python3
"""
factory_logging.py
统一结构化日志系统。

所有 writing-skill-factory-cli 脚本共享同一日志文件，
支持控制台人类可读输出 + 文件 JSON 结构化记录。
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 推导项目根目录（本文件位于 scripts/，项目根目录是其父目录）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG_DIR = str(_PROJECT_ROOT / ".claude" / "writing-factory" / "logs")


class _JSONFormatter(logging.Formatter):
    """将日志记录输出为单行 JSON。"""

    def format(self, record: logging.LogRecord) -> str:
        obj: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # 附加额外字段
        for key in ("child_name", "script", "step", "article_id", "context"):
            val = getattr(record, key, None)
            if val is not None:
                obj[key] = val
        if record.exc_info:
            obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(obj, ensure_ascii=False)


class _HumanFormatter(logging.Formatter):
    """控制台人类可读格式。"""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%H:%M:%S")
        prefix = f"[{ts} {record.levelname:8}]"
        extra = ""
        child = getattr(record, "child_name", None)
        step = getattr(record, "step", None)
        if child and step:
            extra = f" [{child}/{step}]"
        elif child:
            extra = f" [{child}]"
        return f"{prefix}{extra} {record.getMessage()}"


def setup_logger(
    name: str,
    child_name: str | None = None,
    log_dir: str = DEFAULT_LOG_DIR,
    level: int = logging.INFO,
) -> logging.Logger:
    """
    获取并配置一个带统一 handler 的 logger。

    参数:
        name: logger 名称，通常用 __name__ 或脚本名。
        child_name: 当前操作的 child skill 名，会注入到每条记录。
        log_dir: 日志文件存放目录。
        level: 日志级别。
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加 handler（reload 场景）
    if getattr(logger, "_factory_initialized", False):
        return logger

    # 文件 handler -> JSON
    log_path = Path(log_dir) / "factory.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(_JSONFormatter())
    logger.addHandler(fh)

    # 控制台 handler -> 人类可读
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(_HumanFormatter())
    logger.addHandler(ch)

    logger._factory_initialized = True  # type: ignore[attr-defined]
    return logger


class LogContext:
    """
    上下文管理器，用于临时注入 child_name / step 等字段。

    用法:
        with LogContext(logger, child_name="test_writer", step="sync"):
            logger.info("开始同步")
    """

    def __init__(
        self,
        logger: logging.Logger,
        child_name: str | None = None,
        step: str | None = None,
        article_id: str | None = None,
        context: dict[str, Any] | None = None,
    ):
        self.logger = logger
        self.extra = {}
        if child_name is not None:
            self.extra["child_name"] = child_name
        if step is not None:
            self.extra["step"] = step
        if article_id is not None:
            self.extra["article_id"] = article_id
        if context is not None:
            self.extra["context"] = context

    def __enter__(self) -> "LogContext":
        self._adapter = logging.LoggerAdapter(self.logger, self.extra)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    def debug(self, msg: str, *args, **kwargs):
        self._adapter.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        self._adapter.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        self._adapter.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        self._adapter.error(msg, *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs):
        self._adapter.exception(msg, *args, **kwargs)


def log_boundry_event(
    logger: logging.Logger,
    event: str,
    child_name: str,
    details: dict[str, Any] | None = None,
    level: int = logging.INFO,
) -> None:
    """记录一条带边界上下文的关键事件。"""
    payload = {"event": event, "child_name": child_name}
    if details:
        payload.update(details)
    extra = {"child_name": child_name, "context": payload}
    logger.log(level, event, extra=extra)
