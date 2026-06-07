"""web_api.py — Yay の投稿/返信を web JSON API で直接叩く（ブラウザ不要・速い）。

create_post(モバイル form + signed_info)は web 由来トークンでは『Invalid signed info』で
弾かれる。が、Yay web 版が使う JSON 経路は **x-jwt ヘッダ**認証で signed_info も recaptcha も
不要。実機観測で確定:
  POST https://api.yay.space/v3/posts/new
  headers: Authorization: Bearer <web token>, X-Jwt: <HS256 5秒TTL>,
           X-App-Version: 4.26, Agent: YayWeb 4.26, Content-Type: application/json
  body(JSON): {"text","post_type":"text","color":0,"font_size":0[,"in_reply_to"]}
x-jwt の鍵 = yaylib の api_version_key（4.26）。x-app-version も 4.26 に合わせる（鍵とバージョン対）。
"""
import json
import os
import urllib.error
import urllib.request

import yaylib
import yaylib.signing as _sign

HERE = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(os.path.dirname(HERE), ".yay_token")
API = "https://api.yay.space"
VER = "4.26"  # x-jwt 鍵(api_version_key)と対。yaylib のバージョンに合わせる
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36")
_c = yaylib.Client()  # api_version_key を借りるだけ（ネットワーク I/O 無し）


def _token() -> str:
    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def _headers() -> dict:
    return {
        "Authorization": "Bearer " + _token(),
        "X-Jwt": _sign.generate_x_jwt(api_version_key=_c.api_version_key),  # 5秒TTL・毎回生成
        "X-App-Version": VER,
        "Agent": "YayWeb " + VER,
        "X-Device-Info": f"Yay {VER} Web ({_UA})",
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json, text/plain, */*",
    }


def create_post(text: str, in_reply_to=None):
    """投稿/返信を1本作る。戻り値 (ok: bool, post_id or error_str)。"""
    payload = {"text": text, "post_type": "text", "color": 0, "font_size": 0}
    if in_reply_to:
        payload["in_reply_to"] = int(in_reply_to)
    req = urllib.request.Request(
        API + "/v3/posts/new",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST", headers=_headers())
    try:
        r = urllib.request.urlopen(req, timeout=20)
        return True, json.loads(r.read().decode()).get("id")
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code} {e.read().decode()[:120]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def edit_user(nickname: str, biography: str):
    """プロフィール編集（bio 設定）。/v3/users/edit も x-jwt JSON 経路で signed_info 不要。
    nickname を一緒に送らないと消える実装なので現値を渡すこと。戻り (ok, info)。"""
    payload = {"nickname": nickname, "biography": biography}
    req = urllib.request.Request(
        API + "/v3/users/edit",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST", headers=_headers())
    try:
        r = urllib.request.urlopen(req, timeout=20)
        return True, r.read().decode()[:80]
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code} {e.read().decode()[:120]}"


# 投稿削除は yaylib の delete_posts（mobile /v2/posts/mass_destroy）が follow/like 同様に
# 署名チェック無しで web トークンでも通る。web JSON 経路は 403 になるのでそちらは使わない。
