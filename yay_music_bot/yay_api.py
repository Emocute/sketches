#!/usr/bin/env python3
"""yay_api.py — Yay の通話資格情報フェッチャ（yaylib 経由）

全面API移行（2026-06-03）の足回り。ブラウザDOMを廃し、Agora に直接入るための
資格情報（RTC: agora_channel/agora_token、RTM: token）を Yay の公式 API から取る。

認証は **既存トークン流用のみ**（究判断）。`.yay_token` の access token を
yaylib に注入し、oauth 新規ログイン（新デバイス扱い＝不正検知リスク）を避ける。

使い方（node 側から shell out する想定。出力は最終行に JSON 1 行）:
  python3 yay_api.py check                 # トークンが生きてるか（認証必須の軽い口で確認）
  python3 yay_api.py active [user_id]       # 現在参加中の通話を発見 → creds JSON
  python3 yay_api.py creds <call_id>        # call_id 指定で creds JSON
  python3 yay_api.py members <call_id>      # 通話の参加者名簿（入退室あいさつ用）
  python3 yay_api.py leave <conference_id>  # 通話/Agora から離脱

出力 JSON: {ok, app_id, channel, rtc_token, rtm_token, conference_id, uid, ...}
失敗時: {ok:false, error:"...", stage:"..."}
"""
import asyncio
import json
import os
import sys
import uuid

import yaylib

HERE = os.path.dirname(os.path.abspath(__file__))
# 複数アカウント艦隊対応: env でアカウントごとの token/device を切り替える。
#   YAY_TOKEN_FILE / YAY_DEVICE_FILE 未指定なら既定の単一アカ（.yay_token / .yay_device）。
#   相対パス指定は HERE 起点で解決（worker を別 cwd から起動しても安定）。
def _resolve(p, default_name):
    if not p:
        return os.path.join(HERE, default_name)
    return p if os.path.isabs(p) else os.path.join(HERE, p)

TOKEN_FILE = _resolve(os.environ.get("YAY_TOKEN_FILE"), ".yay_token")
DEVICE_FILE = _resolve(os.environ.get("YAY_DEVICE_FILE"), ".yay_device")

# 究が共有した Yay の Agora App ID（通話の RTC/RTM 共通）
AGORA_APP_ID = os.environ.get("YAY_AGORA_APP_ID", "79046b8c9be54945b7f10a4d128d5395")
# Emo Claude の Yay user id（config.mjs selfUserHref /user/11320230 と一致）
SELF_UID = int(os.environ.get("YAY_SELF_UID", "11320230"))
SELF_EMAIL = os.environ.get("YAY_SELF_EMAIL", "")


def _read_token() -> str:
    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def _device_uuid() -> str:
    # device_uuid は毎回同じ値で固定（毎回ランダムだと Yay 側で別デバイス扱い＝検知リスク）。
    # 初回生成して .yay_device に永続化する。
    if os.path.exists(DEVICE_FILE):
        with open(DEVICE_FILE, "r", encoding="utf-8") as f:
            v = f.read().strip()
            if v:
                return v
    v = str(uuid.uuid4())
    with open(DEVICE_FILE, "w", encoding="utf-8") as f:
        f.write(v)
    return v


def _build_client() -> "yaylib.Client":
    c = yaylib.Client()
    c.set_device_uuid(_device_uuid())
    if SELF_EMAIL:
        c.set_login_identity(SELF_EMAIL, SELF_UID)
    c.set_tokens(_read_token(), "")  # refresh は無し（既存 access のみ流用）
    return c


def _emit(obj: dict):
    print(json.dumps(obj, ensure_ascii=False, default=str))


def _conf_to_creds(conf, rtm_token=None) -> dict:
    """RealmConferenceCall → creds dict。agora_channel/agora_token を吸い出す。"""
    return {
        "ok": True,
        "app_id": AGORA_APP_ID,
        "conference_id": getattr(conf, "id", None),
        "channel": getattr(conf, "agora_channel", None),
        "rtc_token": getattr(conf, "agora_token", None),
        "rtm_token": rtm_token,
        "uid": SELF_UID,
    }


async def cmd_check(client) -> dict:
    # 認証必須の軽い口（BGM 一覧）で 200 が返れば token は生きている
    res = await client.get_call_bgms()
    n = len(getattr(res, "bgm", None) or getattr(res, "bgms", None) or [])
    return {"ok": True, "stage": "check", "bgm_count": n, "uid": SELF_UID}


async def _creds_for_call(client, call_id: int) -> dict:
    conf_res = await client.get_conference_call(call_id)
    conf = getattr(conf_res, "conference_call", None)
    if conf is None:
        return {"ok": False, "stage": "get_conference_call", "error": "conference_call が空"}
    rtm = None
    try:
        rtm_res = await client.get_agora_rtm_token(call_id)
        rtm = getattr(rtm_res, "token", None)
    except Exception as e:  # RTM トークンは取れなくても RTC は使えるので致命にしない
        rtm = None
        sys.stderr.write(f"[warn] rtm token 取得失敗: {e}\n")
    out = _conf_to_creds(conf, rtm)
    out["conference_call_user_uuid"] = getattr(conf_res, "conference_call_user_uuid", None)
    return out


async def cmd_creds(client, call_id: int) -> dict:
    return await _creds_for_call(client, call_id)


async def cmd_active(client, user_id: int) -> dict:
    res = await client.get_active_call_post(user_id)
    post = getattr(res, "post", None)
    if post is None:
        return {"ok": False, "stage": "get_active_call_post", "error": "参加中の通話が無い"}
    conf = getattr(post, "conference_call", None)
    call_id = getattr(conf, "id", None) if conf else None
    # post に conference_call が乗っていれば agora_channel/token もそのまま入る
    if conf and getattr(conf, "agora_channel", None) and getattr(conf, "agora_token", None):
        rtm = None
        if call_id:
            try:
                rtm = getattr(await client.get_agora_rtm_token(call_id), "token", None)
            except Exception as e:
                sys.stderr.write(f"[warn] rtm token: {e}\n")
        out = _conf_to_creds(conf, rtm)
        out["post_id"] = getattr(post, "id", None)
        return out
    if call_id:  # 念のため詳細を引き直す
        out = await _creds_for_call(client, call_id)
        out["post_id"] = getattr(post, "id", None)
        return out
    return {"ok": False, "stage": "active", "error": "post に conference_call.id が無い"}


async def cmd_members(client, call_id: int) -> dict:
    """通話の参加者名簿（入退室あいさつ用）。{id, nickname, uuid} の軽量リストを返す。

    bot 側で前回名簿との差分を取り「○○いらっしゃい/またね」を出す。返すのは挨拶に要る
    最小フィールドだけ（会話・人格・聴取は持たない純音楽botの原則を保つ）。
    """
    res = await client.get_conference_call(call_id)
    conf = getattr(res, "conference_call", None)
    if conf is None:
        return {"ok": False, "stage": "get_conference_call", "error": "conference_call が空"}
    users = []
    for u in getattr(conf, "conference_call_users", None) or []:
        users.append({
            "id": getattr(u, "id", None),
            "nickname": getattr(u, "nickname", None),
            "uuid": getattr(u, "uuid", None),
        })
    return {"ok": True, "call_id": call_id, "count": len(users), "users": users}


async def cmd_leave(client, conference_id: int) -> dict:
    await client.leave_conference_call(conference_id=conference_id)
    try:
        await client.leave_agora_channel(conference_id=conference_id, user_id=SELF_UID)
    except Exception:
        pass
    return {"ok": True, "stage": "leave", "conference_id": conference_id}


async def main(argv):
    if not argv:
        _emit({"ok": False, "error": "usage: yay_api.py <check|active|creds|members|leave> [arg]"})
        return 2
    cmd = argv[0]
    client = None
    try:
        client = _build_client()
        if cmd == "check":
            out = await cmd_check(client)
        elif cmd == "active":
            uid = int(argv[1]) if len(argv) > 1 else SELF_UID
            out = await cmd_active(client, uid)
        elif cmd == "creds":
            if len(argv) < 2:
                out = {"ok": False, "error": "creds は call_id が必要"}
            else:
                out = await cmd_creds(client, int(argv[1]))
        elif cmd == "members":
            if len(argv) < 2:
                out = {"ok": False, "error": "members は call_id が必要"}
            else:
                out = await cmd_members(client, int(argv[1]))
        elif cmd == "leave":
            if len(argv) < 2:
                out = {"ok": False, "error": "leave は conference_id が必要"}
            else:
                out = await cmd_leave(client, int(argv[1]))
        else:
            out = {"ok": False, "error": f"unknown cmd: {cmd}"}
    except Exception as e:
        out = {"ok": False, "stage": "exception", "error": f"{type(e).__name__}: {e}"}
    finally:
        if client is not None:
            try:
                await client.close()
            except Exception:
                pass
    _emit(out)
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
