#!/usr/bin/env python3
"""mobile_login.py — Yay モバイル API トークンを email/password で取得して保存する。

X-OAuth アカウントは yaylib の login_with_email が使えないため、Yay アプリ設定で
email+password を追加してから本スクリプトで初回ログインしモバイルトークンを得る。
device_uuid は既存 `.yay_device` を流用（同一デバイス指紋で signed_info を通すため）。

資格情報は**環境変数**で渡す（コマンド履歴・コミット・ログに残さない）:
  YAY_EMAIL='...' YAY_PASSWORD='...' ./.venv/bin/python scripts/mobile_login.py
  （2FA 有効時は YAY_2FA='123456' も）

成功すると `.yay_token.mobile`（gitignore 済 `.yay_token.*`）に保存し、モバイル署名経路の
疎通（create_post を mobile form + signed_info で1本→即削除）まで検証する。
"""
import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import yaylib

DEVICE_FILE = os.path.join(ROOT, ".yay_device")
OUT_FILE = os.path.join(ROOT, ".yay_token.mobile")


async def main():
    email = os.environ.get("YAY_EMAIL")
    pw = os.environ.get("YAY_PASSWORD")
    twofa = os.environ.get("YAY_2FA")
    if not email or not pw:
        print("YAY_EMAIL / YAY_PASSWORD を環境変数で渡してください（PW は出力しません）")
        return 2

    device = open(DEVICE_FILE).read().strip()
    c = yaylib.Client()
    c.set_device_uuid(device)
    kw = {"email": email, "password": pw, "uuid": device}
    if twofa:
        kw["two_fa_code"] = twofa
    try:
        res = await c.login_with_email(**kw)
    except Exception as e:
        print(f"login 失敗: {type(e).__name__}: {str(e).splitlines()[0][:120]}")
        await c.close()
        return 1

    token = getattr(res, "access_token", None) or getattr(res, "token", None)
    if not token:
        print(f"login 応答にトークンが無い: {[a for a in dir(res) if not a.startswith('_')][:15]}")
        await c.close()
        return 1
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(token)
    print(f"✓ モバイルトークン取得・保存 → {os.path.basename(OUT_FILE)} (len={len(token)})")

    # モバイル署名経路の疎通: create_post(mobile form + signed_info) → 即削除
    c2 = yaylib.Client()
    c2.set_device_uuid(device)
    c2.set_tokens(token, getattr(res, "refresh_token", "") or "")
    try:
        post = await c2.create_post(text="（モバイル署名 疎通テスト・自動削除）")
        pid = getattr(post, "id", None)
        print(f"✓ mobile create_post OK (id={pid}) — モバイル署名経路 開通")
        if pid:
            try:
                await c2.delete_posts(posts_ids=[pid])
                print("  テスト投稿は削除済み")
            except Exception:
                print(f"  ※テスト投稿 {pid} の削除は手動で")
    except Exception as e:
        print(f"※ mobile create_post 検証失敗: {type(e).__name__}: {str(e).splitlines()[0][:120]}")
        print("  （トークンは保存済み。follow/like 等は使えるが signed_info 系は要追加調査）")
    await c.close()
    await c2.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
