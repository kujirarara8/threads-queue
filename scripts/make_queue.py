"""クロエの控え（Threads予約_YYYY-MM-DD.md）と画像フォルダから、予約リスト queue/YYYY-MM-DD.json を作る。

  python scripts/make_queue.py <控えの.md> <画像フォルダ>

控えの形：表の「| # | 予約時刻 | ...」で時刻を、「## 1」〜「## 10」の見出しの下で本文を読む。
画像は Threads_YYYYMMDD_<投稿番号2桁>_<枚目2桁>.png を、その投稿の画像として順に付ける。
"""
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(md_path, img_dir):
    with open(md_path, encoding="utf-8") as f:
        md = f.read()
    date = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(md_path)).group(1)

    times = dict(re.findall(r"^\|\s*(\d+)\s*\|\s*(\d{1,2}:\d{2})\s*\|", md, re.M))
    bodies = dict(
        (m.group(1), m.group(2).strip())
        for m in re.finditer(r"^## (\d+)\n(.*?)(?=^## \d+\n|\Z)", md, re.M | re.S)
    )

    dest = os.path.join("images", date)
    os.makedirs(os.path.join(ROOT, dest), exist_ok=True)
    files = sorted(os.listdir(img_dir)) if img_dir else []

    posts = []
    for n in sorted(bodies, key=int):
        imgs = []
        for fn in files:
            m = re.match(r".*_(\d{2})_(\d{2})\.(png|jpe?g)$", fn, re.I)
            if m and int(m.group(1)) == int(n):
                shutil.copy2(os.path.join(img_dir, fn), os.path.join(ROOT, dest, fn))
                imgs.append(f"{dest}/{fn}")
        posts.append({"id": n.zfill(2), "time": times[n].zfill(5), "text": bodies[n], "images": imgs})

    out = os.path.join(ROOT, "queue", f"{date}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"date": date, "posts": posts}, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"{out}: {len(posts)}本（画像つき {sum(1 for p in posts if p['images'])}本）")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
