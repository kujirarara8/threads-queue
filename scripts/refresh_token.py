"""長期トークン（60日）を延ばして state/token.enc に暗号化して保存する。週1回 GitHub Actions から呼ばれる。"""
from threads import API, load_token, save_token
import json
import urllib.parse
import urllib.request


def main():
    token = load_token()
    q = urllib.parse.urlencode({"grant_type": "th_refresh_token", "access_token": token})
    with urllib.request.urlopen(f"{API.rsplit('/', 1)[0]}/refresh_access_token?{q}", timeout=60) as r:
        res = json.load(r)
    save_token(res["access_token"])
    print(f"トークンを延長しました（あと約{int(res.get('expires_in', 0)) // 86400}日）")


if __name__ == "__main__":
    main()
