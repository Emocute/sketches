#!/usr/bin/env python3
"""grow.py — Yay フォロワー成長 bot（grok 型・何でも答える AI／攻め度=中）

通話 bot（bot_agora.mjs / Agora 常駐）とは**完全に独立した別プロセス**。API のみで動く
ので、通話 bot を一切落とさず並走できる（[[feedback_yay_bot_no_restart]] を侵さない）。

やること（grok の運用を再現）:
  1) 自動フォロバ        — 通知(activity)の follow を拾って follow_user で返す
  2) メンション返信      — 自分宛の reply/mention を拾い、grok 型ペルソナで返信
  3) 能動リプ＋いいね    — おすすめ timeline の投稿に絡みに行く（露出→発見→フォロー）

安全弁:
  - dry_run=true（既定）の間は**書き込みを一切しない**。何をするかをログに出すだけ。
  - レート制限（時間あたり上限）＋アクション間スロットル（最短間隔＋ゆらぎ）＋quiet hours。
  - 返信生成の claude -p は中立 cwd(tmpdir)＋ツール無し（CLAUDE.md を読まない＝思考漏れ防止）。
  - 認証は .yay_token の既存アクセストークン流用のみ（新規 oauth=新デバイス検知を避ける）。

使い方:
  python3 social/grow.py --check          # トークン生存＋自分の現状(フォロワー数)
  python3 social/grow.py --once           # 1パスだけ（cron 向き／dry-run 確認向き）
  python3 social/grow.py                  # 常駐ループ
  python3 social/grow.py --set-bio        # bio を social/bio.txt の内容に設定（要 dry_run=false）
"""
import argparse
import asyncio
import json
import os
import random
import subprocess
import sys
import time

import yaylib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # yay_bot/
TOKEN_FILE = os.path.join(ROOT, ".yay_token")
DEVICE_FILE = os.path.join(ROOT, ".yay_device")
CONFIG_FILE = os.path.join(HERE, "config.json")
STATE_FILE = os.path.join(HERE, "state.json")
PERSONA_FILE = os.path.join(HERE, "persona.txt")
BIO_FILE = os.path.join(HERE, "bio.txt")

AGORA_APP_ID = os.environ.get("YAY_AGORA_APP_ID", "79046b8c9be54945b7f10a4d128d5395")


# ───────────────────────── 基盤 ─────────────────────────

def log(msg: str):
    t = time.strftime("%H:%M:%S")
    print(f"[{t}] {msg}", flush=True)


def load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_state(state: dict):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


def build_client() -> "yaylib.Client":
    c = yaylib.Client()
    with open(DEVICE_FILE, "r", encoding="utf-8") as f:
        c.set_device_uuid(f.read().strip())
    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
        c.set_tokens(f.read().strip(), "")
    return c


# ───────────────────────── レート制限 / スロットル ─────────────────────────

class Limiter:
    """時間あたり上限（直近1時間のアクション時刻を保持）＋アクション間スロットル。"""

    def __init__(self, state: dict, cfg: dict):
        self.state = state
        self.cfg = cfg
        self.state.setdefault("hits", {})       # bucket -> [epoch, ...]
        self.state.setdefault("last_action", 0)  # 直近の書き込み時刻

    def _recent(self, bucket: str) -> int:
        now = time.time()
        arr = [t for t in self.state["hits"].get(bucket, []) if now - t < 3600]
        self.state["hits"][bucket] = arr
        return len(arr)

    def allow(self, bucket: str, cap: int) -> bool:
        return self._recent(bucket) < cap

    def record(self, bucket: str):
        self.state["hits"].setdefault(bucket, []).append(time.time())
        self.state["last_action"] = time.time()

    async def throttle(self):
        """アクション間の最短間隔＋ゆらぎを守る（書き込み前に必ず呼ぶ）。"""
        th = self.cfg["throttle"]
        gap = th["min_action_gap_sec"] + random.uniform(0, th.get("jitter_sec", 0))
        wait = gap - (time.time() - self.state.get("last_action", 0))
        if wait > 0:
            await asyncio.sleep(wait)


def in_quiet_hours(cfg: dict) -> bool:
    lo, hi = cfg.get("quiet_hours", [99, 99])
    h = int(time.strftime("%H"))
    return lo <= h < hi if lo <= hi else (h >= lo or h < hi)


# ───────────────────────── 返信生成（claude -p / 中立 cwd） ─────────────────────────

def gen_reply(persona: str, asker: str, text: str, cfg: dict) -> str:
    """grok 型ペルソナで返信本文を作る。出力の 'REPLY:' 以降だけ採用。"""
    import tempfile
    prompt = (
        f"{persona}\n\n"
        f"---\n"
        f"{asker} さんからの投稿/メンション:\n「{text}」\n\n"
        f"これに上のキャラクターで返信せよ。255文字以内。最後に必ず『REPLY: 』に続けて本文だけ書く。"
    )
    env = dict(os.environ)
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)
    model = cfg.get("claude_model", "claude-opus-4-8")
    timeout = cfg.get("reply_timeout_ms", 60000) / 1000.0
    try:
        out = subprocess.run(
            ["claude", "-p", prompt, "--model", model, "--strict-mcp-config"],
            cwd=tempfile.gettempdir(), env=env,
            capture_output=True, text=True, timeout=timeout,
        ).stdout
    except subprocess.TimeoutExpired:
        log("  reply gen timeout")
        return ""
    low = out.rfind("REPLY:")
    body = (out[low + 6:] if low >= 0 else out).strip()
    return body[:255]


# ───────────────────────── 書き込みアクション（dry_run ゲート） ─────────────────────────

async def do_follow(client, lim, cfg, state, uid: int, nick: str):
    if uid in state["followed"] or uid == cfg["self_uid"] or uid in cfg.get("skip_users", []):
        return False
    if not lim.allow("follow", cfg["followback"]["max_per_hour"]):
        log(f"  [skip] follow cap reached (uid={uid})")
        return False
    if cfg["dry_run"]:
        log(f"  [DRY] follow {nick}({uid})")
        state["followed"].append(uid)
        return True
    await lim.throttle()
    try:
        await client.follow_user(uid)
        lim.record("follow")
        state["followed"].append(uid)
        log(f"  ✓ followed {nick}({uid})")
        return True
    except Exception as e:
        log(f"  ! follow {uid} failed: {type(e).__name__} {e}")
        return False


async def do_reply(client, lim, cfg, state, bucket: str, cap: int, post_id: int, uid: int, nick: str, text: str, persona: str):
    if post_id in state["replied"]:
        return False
    if not lim.allow(bucket, cap):
        log(f"  [skip] {bucket} cap reached (post={post_id})")
        return False
    body = gen_reply(persona, nick, text, cfg)
    if not body:
        log(f"  [skip] empty reply (post={post_id})")
        return False
    mention = f"@{nick} " if nick else ""
    full = (mention + body)[:255]
    if cfg["dry_run"]:
        log(f"  [DRY] reply→{nick}({uid}) post#{post_id}: {full[:80]}")
        state["replied"].append(post_id)
        return True
    await lim.throttle()
    try:
        try:
            await client.create_post(text=full, in_reply_to=post_id, mention_ids=[uid])
        except TypeError:
            await client.create_post(text=full, in_reply_to=post_id)
        lim.record(bucket)
        state["replied"].append(post_id)
        log(f"  ✓ replied→{nick} post#{post_id}: {full[:60]}")
        return True
    except Exception as e:
        log(f"  ! reply post#{post_id} failed: {type(e).__name__} {e}")
        return False


async def do_like(client, lim, cfg, state, post_id: int):
    if post_id in state["liked"]:
        return False
    if not lim.allow("like", cfg["proactive"]["max_likes_per_hour"]):
        return False
    if cfg["dry_run"]:
        log(f"  [DRY] like post#{post_id}")
        state["liked"].append(post_id)
        return True
    await lim.throttle()
    try:
        await client.like_posts([post_id])
        lim.record("like")
        state["liked"].append(post_id)
        return True
    except Exception as e:
        log(f"  ! like post#{post_id} failed: {type(e).__name__} {e}")
        return False


# ───────────────────────── ジョブ ─────────────────────────

def _post_fields(p):
    return (
        getattr(p, "id", None),
        getattr(getattr(p, "user", None), "id", None),
        getattr(getattr(p, "user", None), "nickname", None) or "誰か",
        (getattr(p, "text", "") or "").strip(),
    )


async def job_activities(client, lim, cfg, state, persona):
    """通知 feed を1パス処理: follow→フォロバ / reply・mention→返信。未知 type はログ。"""
    try:
        res = await client.get_user_activities_v1(important=False, number=40)
    except Exception as e:
        log(f"activities fetch failed: {type(e).__name__} {e}")
        return
    acts = getattr(res, "activities", None) or []
    reply_types = set(cfg["mention_reply"]["reply_types"])
    new_seen = 0
    for a in reversed(acts):  # 古い順に処理
        aid = getattr(a, "id", None)
        atype = getattr(a, "type", None)
        if isinstance(atype, dict):
            atype = atype.get("type") or atype.get("name") or str(atype)
        key = f"a{aid}" if aid is not None else f"t{atype}:{getattr(a,'created_at_millis',0)}"
        if key in state["seen_act"]:
            continue
        state["seen_act"].append(key)
        new_seen += 1

        # 1) フォロバ
        if cfg["followback"]["enabled"] and atype == "follow":
            for u in (getattr(a, "followers", None) or ([getattr(a, "user", None)] if getattr(a, "user", None) else [])):
                if u is None:
                    continue
                await do_follow(client, lim, cfg, state, getattr(u, "id", None), getattr(u, "nickname", "") or "")
            continue

        # 2) メンション/返信に返す
        if cfg["mention_reply"]["enabled"] and atype in reply_types:
            fp = getattr(a, "from_post", None)
            if fp is None:
                log(f"  [info] {atype}: from_post 無し（要calibrate）")
                continue
            pid, uid, nick, text = _post_fields(fp)
            if pid and uid and uid != cfg["self_uid"]:
                await do_reply(client, lim, cfg, state, "mreply",
                               cfg["mention_reply"]["max_per_hour"], pid, uid, nick, text, persona)
            continue

        # 3) 未知 type は calibrate 用にログ（from_post があるか含めて）
        has_fp = getattr(a, "from_post", None) is not None
        log(f"  [type] '{atype}' (from_post={has_fp}) ← reply_types に足すか判断")

    if new_seen:
        log(f"activities: {new_seen} new processed (followed={len(state['followed'])}, replied={len(state['replied'])})")
    # seen 配列の肥大を抑える
    for k in ("seen_act", "followed", "replied", "liked"):
        if len(state[k]) > 4000:
            state[k] = state[k][-2000:]


async def job_proactive(client, lim, cfg, state, persona):
    """おすすめ timeline に絡みに行く（いいね＋一部に返信）。露出→発見→フォロー導線。"""
    pc = cfg["proactive"]
    if not pc.get("enabled"):
        return
    if in_quiet_hours(cfg):
        return
    try:
        if pc.get("source") == "tag" and pc.get("tags"):
            tag = random.choice(pc["tags"])
            res = await client.get_posts_by_tag(tag=tag, number=pc["max_targets_per_cycle"])
            log(f"proactive source=#{tag}")
        else:
            res = await client.get_recommended_timeline(
                experiment_num=pc.get("experiment_num", 1),
                variant_num=pc.get("variant_num", 1),
                number=pc["max_targets_per_cycle"])
    except Exception as e:
        log(f"proactive fetch failed: {type(e).__name__} {e}")
        return
    posts = getattr(res, "posts", None) or []
    n_like = n_reply = 0
    for p in posts:
        pid, uid, nick, text = _post_fields(p)
        if not pid or not uid or uid == cfg["self_uid"] or uid in cfg.get("skip_users", []):
            continue
        if await do_like(client, lim, cfg, state, pid):
            n_like += 1
        if text and random.random() < pc.get("reply_ratio", 0.0):
            if await do_reply(client, lim, cfg, state, "preply",
                              pc["max_replies_per_hour"], pid, uid, nick, text, persona):
                n_reply += 1
    if n_like or n_reply:
        log(f"proactive: liked={n_like} replied={n_reply}")


# ───────────────────────── メイン ─────────────────────────

DEFAULT_STATE = {"seen_act": [], "followed": [], "replied": [], "liked": [], "hits": {}, "last_action": 0}


async def cmd_check(client, cfg):
    bgm = await client.get_call_bgms()
    n = len(getattr(bgm, "bgm", None) or getattr(bgm, "bgms", None) or [])
    u = await client.get_user(cfg["self_uid"])
    user = getattr(u, "user", u)
    log(f"token OK (bgm={n}). SELF '{getattr(user,'nickname','?')}' "
        f"followers={getattr(user,'followers_count','?')} posts={getattr(user,'posts_count','?')}")


async def cmd_set_bio(client, cfg):
    if not os.path.exists(BIO_FILE):
        log(f"bio.txt が無い: {BIO_FILE}")
        return
    bio = open(BIO_FILE, encoding="utf-8").read().strip()
    if cfg["dry_run"]:
        log(f"[DRY] set bio ({len(bio)}字):\n{bio}")
        return
    # nickname を一緒に送らないと空になる実装があるので現値を保持して渡す
    u = await client.get_user(cfg["self_uid"])
    nick = getattr(getattr(u, "user", u), "nickname", None) or "Claude"
    si = await client.generate_signed_info()  # 改竄防止署名（timestamp と対）
    try:
        await client.edit_user(nickname=nick, biography=bio,
                               signed_info=si.value, timestamp=si.timestamp)
        log(f"✓ bio updated (nickname 保持='{nick}')")
    except Exception as e:
        log(f"! set bio failed: {type(e).__name__} {e}")


async def run_loop(once: bool):
    cfg = load_json(CONFIG_FILE, {})
    persona = open(PERSONA_FILE, encoding="utf-8").read() if os.path.exists(PERSONA_FILE) else ""
    state = load_json(STATE_FILE, dict(DEFAULT_STATE))
    for k, v in DEFAULT_STATE.items():
        state.setdefault(k, v if not isinstance(v, list) else [])
    lim = Limiter(state, cfg)

    mode = "DRY-RUN（書き込みなし）" if cfg.get("dry_run", True) else "LIVE（実発射）"
    log(f"=== grow.py start [{mode}] 攻め度=中 ===")

    client = build_client()
    next_engage = 0.0
    try:
        while True:
            await job_activities(client, lim, cfg, state, persona)
            if time.time() >= next_engage:
                await job_proactive(client, lim, cfg, state, persona)
                next_engage = time.time() + cfg["poll"]["engage_min"] * 60
            save_state(state)
            if once:
                log("=== --once done ===")
                break
            await asyncio.sleep(cfg["poll"]["activity_sec"])
    finally:
        save_state(state)
        try:
            await client.close()
        except Exception:
            pass


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--set-bio", action="store_true", dest="set_bio")
    args = ap.parse_args()

    cfg = load_json(CONFIG_FILE, {})
    if args.check or args.set_bio:
        client = build_client()
        try:
            if args.check:
                await cmd_check(client, cfg)
            if args.set_bio:
                await cmd_set_bio(client, cfg)
        finally:
            await client.close()
        return
    await run_loop(once=args.once)


if __name__ == "__main__":
    asyncio.run(main())
