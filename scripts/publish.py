"""時刻が来た投稿を公開する。GitHub Actions から15分ごとに呼ばれる。

  python scripts/publish.py            # 公開する
  python scripts/publish.py --check    # 今日と明日の予約リストを確かめるだけ（投稿しない）
"""
import sys
from datetime import datetime, timedelta

from threads import JST, load_posted, load_queue, load_token, now_jst, publish, save_posted, validate

# 時刻から3時間を過ぎた投稿は出さない（止まっていた後にまとめて出ないように）
LATE_LIMIT = timedelta(hours=3)


def check():
    ok = True
    for d in (now_jst().date(), now_jst().date() + timedelta(days=1)):
        q = load_queue(d.isoformat())
        if q is None:
            print(f"{d}: 予約リストなし")
            continue
        problems = validate(q)
        print(f"{d}: {len(q.get('posts', []))}本", "OK" if not problems else "")
        for p in problems:
            print("  -", p)
        ok = ok and not problems
    return ok


def main():
    if "--check" in sys.argv:
        sys.exit(0 if check() else 1)

    now = now_jst()
    date = now.date().isoformat()
    q = load_queue(date)
    if q is None:
        print(f"{date}: 予約リストなし")
        return
    problems = validate(q)
    if problems:
        raise SystemExit("予約リストに問題があります:\n" + "\n".join(problems))

    posted = load_posted()
    due = []
    failed = []
    for p in q["posts"]:
        key = f"{date}/{p['id']}"
        at = datetime.strptime(f"{date} {p['time']}", "%Y-%m-%d %H:%M").replace(tzinfo=JST)
        if key in posted or at > now:
            continue
        if now - at > LATE_LIMIT:
            print(f"{key} は{p['time']}から3時間を過ぎたので出しません")
            posted[key] = {"skipped": "late", "at": now.isoformat(timespec="minutes")}
            failed.append(f"{key}: 時刻から3時間を過ぎたので出していません")
            continue
        due.append((key, p))

    if not due:
        print("今出す投稿はありません")
        save_posted(posted)
        if failed:
            raise SystemExit("\n".join(failed))
        return

    token = load_token()
    for key, p in due:
        try:
            tid = publish(p, token)
            posted[key] = {"thread_id": tid, "at": now_jst().isoformat(timespec="minutes")}
            print(f"公開 {key} ({p['time']}) -> {tid}")
        except Exception as e:  # 1本の失敗で残りを止めない
            failed.append(f"{key}: {e}")
        save_posted(posted)

    if failed:
        raise SystemExit("公開に失敗:\n" + "\n".join(failed))


if __name__ == "__main__":
    main()
