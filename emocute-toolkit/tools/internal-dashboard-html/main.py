"""internal-dashboard-html — toolkit 状況を 1 ページ HTML ダッシュボードに.

phase 進捗 / status_counts / 最近の log を縦に並べた読み専用ページ生成。
"""
from __future__ import annotations
import argparse
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _shared import logger  # noqa: E402

TOOL_ID = "internal-dashboard-html"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="emocute internal dashboard-html")
    p.add_argument("-o", "--out", default="emocute-toolkit-dashboard.html")
    return p


def parse_status(text: str) -> dict:
    out = {"total": 0, "planned": 0, "implemented": 0, "in_progress": 0,
           "deprecated": 0, "phases": {}, "by_category": {}}
    m = re.search(r"  total: (\d+)", text)
    if m: out["total"] = int(m.group(1))
    for key in ["planned", "implemented", "in_progress", "deprecated"]:
        m = re.search(rf"    {key}: (\d+)", text)
        if m: out[key] = int(m.group(1))
    # categories
    cats: dict[str, dict[str, int]] = {}
    for m in re.finditer(r"  ([a-z\-]+): \{ phase: \d+, category: (\w+), priority: \w+, status: (\w+) \}", text):
        cat = m.group(2); st = m.group(3)
        cats.setdefault(cat, {}).setdefault(st, 0)
        cats[cat][st] += 1
    out["by_category"] = cats
    return out


def render_html(s: dict, logs: list[dict]) -> str:
    progress = (s["implemented"] / s["total"] * 100) if s["total"] else 0
    cat_rows = ""
    for cat, counts in sorted(s["by_category"].items()):
        impl = counts.get("implemented", 0)
        plan = counts.get("planned", 0)
        total = impl + plan + counts.get("in_progress", 0)
        pct = impl / total * 100 if total else 0
        cat_rows += (f"<tr><td>{cat}</td>"
                     f"<td>{impl}/{total}</td>"
                     f"<td><div class='bar'><div class='bar-fill' style='width:{pct}%'></div></div> {pct:.0f}%</td></tr>")
    log_rows = ""
    for e in logs[-30:]:
        ts = html.escape(e.get("ts", ""))
        t = html.escape(e.get("type", ""))
        pj = html.escape(e.get("pj", ""))
        msg = html.escape(e.get("message", ""))[:200]
        log_rows += f"<tr><td>{ts}</td><td>{t}</td><td>{pj}</td><td>{msg}</td></tr>"
    return f"""<!doctype html>
<html><head>
<meta charset="utf-8">
<title>emocute toolkit dashboard</title>
<style>
body {{ font-family: -apple-system, sans-serif; max-width: 1000px; margin: 2em auto; padding: 0 1em; color: #ddd; background: #111; }}
h1, h2 {{ color: #fff; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
th, td {{ padding: 6px 12px; border-bottom: 1px solid #333; text-align: left; }}
.bar {{ display: inline-block; width: 100px; height: 8px; background: #333; border-radius: 4px; vertical-align: middle; }}
.bar-fill {{ height: 100%; background: #4caf50; border-radius: 4px; }}
.kpi {{ display: inline-block; background: #222; padding: 1em 1.5em; margin: 0.5em; border-radius: 6px; }}
.kpi-num {{ font-size: 2em; color: #fff; }}
.kpi-label {{ font-size: 0.85em; color: #888; }}
.note {{ font-size: 0.85em; color: #666; }}
</style>
</head><body>
<h1>emocute toolkit</h1>
<p class="note">generated {dt.datetime.now().isoformat(timespec='seconds')}</p>

<div class="kpi"><div class="kpi-num">{s['implemented']}</div><div class="kpi-label">implemented</div></div>
<div class="kpi"><div class="kpi-num">{s['planned']}</div><div class="kpi-label">planned</div></div>
<div class="kpi"><div class="kpi-num">{s['total']}</div><div class="kpi-label">total</div></div>
<div class="kpi"><div class="kpi-num">{progress:.1f}%</div><div class="kpi-label">progress</div></div>

<h2>by category</h2>
<table><thead><tr><th>category</th><th>impl/total</th><th>progress</th></tr></thead>
<tbody>{cat_rows}</tbody></table>

<h2>recent log (last 30)</h2>
<table><thead><tr><th>ts</th><th>type</th><th>pj</th><th>message</th></tr></thead>
<tbody>{log_rows}</tbody></table>
</body></html>
"""


def run(args: argparse.Namespace) -> int:
    root = Path(__file__).resolve().parents[2]
    status_yaml = root / "registry/_status.yaml"
    if not status_yaml.exists():
        logger.error(TOOL_ID, f"not found: {status_yaml}")
        return 2
    s = parse_status(status_yaml.read_text())
    log_path = root / "automation/log.jsonl"
    logs = []
    if log_path.exists():
        for line in log_path.read_text().splitlines()[-200:]:
            try:
                logs.append(json.loads(line))
            except Exception:
                pass
    out = Path(args.out).expanduser().resolve()
    out.write_text(render_html(s, logs))
    print(f"✅ wrote {out}")
    logger.done(TOOL_ID, f"dashboard -> {out.name}")
    return 0


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except Exception as e:
        logger.error(TOOL_ID, f"crashed: {e}")
        raise


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
