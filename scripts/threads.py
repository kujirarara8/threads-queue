"""Threads API と予約リストの共通処理（標準ライブラリだけで動く）。"""
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://graph.threads.net/v1.0"
JST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_ENC = os.path.join(ROOT, "state", "token.enc")
POSTED = os.path.join(ROOT, "state", "posted.json")
MAX_TEXT = 500


def now_jst():
    return datetime.now(JST)


def raw_url(path):
    repo = os.environ.get("GITHUB_REPOSITORY", "kujirarara8/threads-queue")
    return f"https://raw.githubusercontent.com/{repo}/main/{urllib.parse.quote(path)}"


# --- トークン -----------------------------------------------------------
# 延長したトークンは TOKEN_KEY で暗号化して state/token.enc に置く。
# まだ無い時（初回）は Secrets の THREADS_TOKEN を使う。

def _openssl(args, data):
    key = os.environ["TOKEN_KEY"]
    return subprocess.run(
        ["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "200000", "-a", "-A", *args, "-pass", "env:TOKEN_KEY"],
        input=data, capture_output=True, check=True, env={**os.environ, "TOKEN_KEY": key},
    ).stdout


def load_token():
    if os.path.exists(TOKEN_ENC) and os.environ.get("TOKEN_KEY"):
        with open(TOKEN_ENC, "rb") as f:
            return _openssl(["-d"], f.read()).decode().strip()
    token = os.environ.get("THREADS_TOKEN", "").strip()
    if not token:
        raise SystemExit("トークンがありません（Secrets の THREADS_TOKEN を設定してください）")
    return token


def save_token(token):
    os.makedirs(os.path.dirname(TOKEN_ENC), exist_ok=True)
    with open(TOKEN_ENC, "wb") as f:
        f.write(_openssl([], token.encode()))


# --- API ---------------------------------------------------------------

def call(method, path, token, **params):
    params["access_token"] = token
    data = urllib.parse.urlencode(params).encode()
    url = f"{API}/{path}"
    if method == "GET":
        req = urllib.request.Request(f"{url}?{data.decode()}")
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"{method} {path} -> {e.code}: {body}") from None


def wait_ready(container_id, token, tries=30):
    for _ in range(tries):
        st = call("GET", container_id, token, fields="status,error_message")
        if st.get("status") == "FINISHED":
            return
        if st.get("status") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"container {container_id}: {st}")
        time.sleep(5)
    raise RuntimeError(f"container {container_id} が準備できませんでした")


def publish(post, token):
    """1投稿を公開して投稿IDを返す。画像が2枚以上ならカルーセル。"""
    images = post.get("images") or []
    if not images:
        c = call("POST", "me/threads", token, media_type="TEXT", text=post["text"])
    elif len(images) == 1:
        c = call("POST", "me/threads", token, media_type="IMAGE", image_url=raw_url(images[0]), text=post["text"])
    else:
        children = []
        for img in images:
            item = call("POST", "me/threads", token, media_type="IMAGE", image_url=raw_url(img), is_carousel_item="true")
            wait_ready(item["id"], token)
            children.append(item["id"])
        c = call("POST", "me/threads", token, media_type="CAROUSEL", children=",".join(children), text=post["text"])
    wait_ready(c["id"], token)
    return call("POST", "me/threads_publish", token, creation_id=c["id"])["id"]


# --- 予約リスト -----------------------------------------------------------

def load_queue(date):
    path = os.path.join(ROOT, "queue", f"{date}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate(q):
    """予約リストの形と中身を確かめ、問題の一覧を返す。"""
    problems = []
    seen = set()
    for p in q.get("posts", []):
        pid = p.get("id")
        if not pid or pid in seen:
            problems.append(f"id が無いか重複: {pid}")
        seen.add(pid)
        try:
            datetime.strptime(p.get("time", ""), "%H:%M")
        except ValueError:
            problems.append(f"{pid}: time は HH:MM で書く")
        if not p.get("text"):
            problems.append(f"{pid}: 本文が空")
        elif len(p["text"]) > MAX_TEXT:
            problems.append(f"{pid}: 本文が{len(p['text'])}字（500字まで）")
        imgs = p.get("images") or []
        if len(imgs) > 20:
            problems.append(f"{pid}: 画像は20枚まで")
        for img in imgs:
            if not os.path.exists(os.path.join(ROOT, img)):
                problems.append(f"{pid}: 画像が無い {img}")
    return problems


def load_posted():
    if os.path.exists(POSTED):
        with open(POSTED, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_posted(posted):
    os.makedirs(os.path.dirname(POSTED), exist_ok=True)
    with open(POSTED, "w", encoding="utf-8") as f:
        json.dump(posted, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
