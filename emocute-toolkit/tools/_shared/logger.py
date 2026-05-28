"""共有ロガー。automation/log.jsonl と ~/.claude/notifications/log.jsonl の両方に追記。

dashboard は ~/.claude/notifications/log.jsonl を 2 秒ポーリングしているので、
toolkit 実行も既存通知ビューアに自動的に流れる。
"""
from __future__ import annotations
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

TOOLKIT_ROOT = Path(__file__).resolve().parents[2]
TOOLKIT_LOG = TOOLKIT_ROOT / "automation" / "log.jsonl"
CLAUDE_NOTIFICATIONS_LOG = Path.home() / ".claude" / "notifications" / "log.jsonl"


def _ts() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def log(tool: str, level: str, msg: str, *, pj: str | None = None, meta: dict[str, Any] | None = None) -> None:
    """toolkit + Claude notifications の両方に追記。

    level: info | warn | error | done
    """
    rec = {
        "ts": _ts(),
        "type": level,
        "tool": tool,
        "pj": pj or os.path.basename(os.getcwd()),
        "message": msg,
    }
    if meta:
        rec["meta"] = meta

    TOOLKIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with TOOLKIT_LOG.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # 通知ビューア側にも流す（存在すれば）
    if CLAUDE_NOTIFICATIONS_LOG.parent.exists():
        try:
            with CLAUDE_NOTIFICATIONS_LOG.open("a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except OSError:
            pass


def info(tool: str, msg: str, **kw): log(tool, "info", msg, **kw)
def warn(tool: str, msg: str, **kw): log(tool, "warn", msg, **kw)
def error(tool: str, msg: str, **kw): log(tool, "error", msg, **kw)
def done(tool: str, msg: str, **kw): log(tool, "done", msg, **kw)
