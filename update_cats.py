#!/usr/bin/env python3
"""
公式ページ（Yell World「ご当地！ころころにゃんこ」）から
 「地域」「名前」だけを読み取って cats.json を更新するスクリプト。

  * 画像は取得も保存もしません（著作権への配慮）。
  * 標準ライブラリだけで動きます（pip install 不要）。
  * 新しく見つかったにゃんこには added（追加日）が付き、サイト側で NEW 表示になります。
  * 公式ページから消えたにゃんこも cats.json には残します（記録が消えないように）。

使い方:
  python update_cats.py                          # cats.json を更新
  python update_cats.py --html index.html        # index.html 内の埋め込みデータも更新
  python update_cats.py --dry-run                # 書き込まず、追加分だけ表示
  python update_cats.py --from-file page.html    # 保存したHTMLから読む（テスト用）
"""
import argparse
import datetime
import html
import json
import re
import sys
import urllib.request
from html.parser import HTMLParser

URL = "https://yell-world.jp/gotouchi-korokoronyanko/"
USER_AGENT = "korokoro-map-updater/1.0 (personal hobby project; text only)"
MIN_EXPECTED = 30  # これ未満しか取れなかったらページ構造が変わったとみなして中止

# ---- 位置（緯度, 経度）。キーは「限定」「県」を除き空白も除いた形 ----------------
AREA_POS = {
    # 都道府県（県庁所在地あたり）
    "北海道": (43.06, 141.35), "青森": (40.82, 140.74), "岩手": (39.70, 141.15),
    "宮城": (38.27, 140.87), "秋田": (39.72, 140.10), "山形": (38.24, 140.36),
    "福島": (37.75, 140.47), "茨城": (36.34, 140.45), "栃木": (36.57, 139.88),
    "群馬": (36.39, 139.06), "埼玉": (35.86, 139.65), "千葉": (35.60, 140.12),
    "東京": (35.68, 139.65), "神奈川": (35.45, 139.64), "新潟": (37.92, 139.04),
    "富山": (36.70, 137.21), "石川": (36.59, 136.63), "福井": (36.07, 136.22),
    "山梨": (35.66, 138.57), "長野": (36.65, 138.18), "岐阜": (35.39, 136.72),
    "静岡": (34.98, 138.38), "愛知": (35.18, 136.91), "三重": (34.73, 136.51),
    "滋賀": (35.00, 135.87), "京都": (35.01, 135.77), "大阪": (34.69, 135.50),
    "兵庫": (34.69, 135.18), "奈良": (34.69, 135.83), "和歌山": (34.23, 135.17),
    "鳥取": (35.50, 134.24), "島根": (35.47, 133.05), "岡山": (34.66, 133.93),
    "広島": (34.40, 132.46), "山口": (34.19, 131.47), "徳島": (34.07, 134.56),
    "香川": (34.34, 134.04), "愛媛": (33.84, 132.77), "高知": (33.56, 133.53),
    "福岡": (33.59, 130.40), "佐賀": (33.25, 130.30), "長崎": (32.75, 129.88),
    "熊本": (32.79, 130.74), "大分": (33.24, 131.61), "宮崎": (31.91, 131.42),
    "鹿児島": (31.60, 130.56), "沖縄": (26.21, 127.68),
    # 都市・施設・エリア
    "三陸": (39.40, 141.90), "五稜郭タワー": (41.80, 140.75),
    "あしかがフラワーパーク": (36.31, 139.52), "アクアワールド大洗水族館": (36.31, 140.57),
    "那須": (37.02, 140.00), "信州": (36.65, 138.18), "飛騨": (36.15, 137.25),
    "富士山付近": (35.36, 138.73), "名古屋": (35.18, 136.91), "神戸": (34.69, 135.20),
    "瀬戸内": (34.35, 133.30), "北九州": (33.88, 130.88), "別府": (33.28, 131.49),
    "八重山石垣島": (24.34, 124.16), "桔梗屋": (35.66, 138.57), "東海": (35.18, 136.91),
    "温泉地": (36.00, 138.00), "地域": (35.50, 138.70),
    "東京・山梨・静岡": (35.50, 138.70), "長野・山梨": (35.90, 138.40),
}
NO_SUBSTR = {"地域"}  # 部分一致では使わない（誤爆防止）

# 特定の施設・スポットに置きたいもの（名前で上書き）
NAME_POS = {
    "東京タワーにゃん": (35.66, 139.75),
    "東京スカイツリーにゃん": (35.71, 139.81),
    "通天閣にゃん": (34.65, 135.51),
    "だざいふうめにゃん": (33.52, 130.52),
    "江ノ電にゃん": (35.32, 139.55),
}

# 公式ページのエリア見出しが読めなかったときの代替位置
REGION_POS = {
    "北海道・東北": (40.0, 141.0), "関東": (36.0, 139.7), "中部": (36.2, 137.5),
    "近畿": (34.8, 135.6), "中国・四国": (34.2, 132.8), "九州・沖縄": (32.5, 130.8),
    "地域限定": (35.7, 137.8),
}


def norm(s):
    s = html.unescape(s or "")
    for ch in ("\u200b", "\ufeff"):
        s = s.replace(ch, "")
    s = s.replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", s).strip()


class Page(HTMLParser):
    """見出し（h1〜h6）の「【地域】名前」と、エリアバナー画像の alt から地方名を読む。"""

    HEADS = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.region = None
        self.items = []  # (region, area, name)
        self._h = None
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            alt = dict(attrs).get("alt") or ""
            m = re.search(r"エリアバナー\s*(.+)", alt)
            if m:
                self.region = norm(m.group(1))
        elif tag in self.HEADS:
            self._h = tag
            self._buf = []

    def handle_data(self, data):
        if self._h:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if self._h and tag == self._h:
            text = norm("".join(self._buf))
            self._h = None
            m = re.match(r"^【([^】]+)】\s*(.+)$", text)
            if m:
                area, name = norm(m.group(1)), norm(m.group(2))
                if name and not re.search(r"\.(jpe?g|png|gif|webp)$", name, re.I):
                    self.items.append((self.region, area, name))


def parse(html_text):
    p = Page()
    p.feed(html_text)
    seen, out = set(), []
    for region, area, name in p.items:
        if (area, name) in seen:
            continue
        seen.add((area, name))
        out.append((region, area, name))
    return out


def locate(area, name, region):
    """(lat, lng, approx) を返す。approx=True は「目安の位置」。"""
    if name in NAME_POS:
        return (*NAME_POS[name], False)
    key = re.sub(r"\s+", "", area)
    cands = [key, key.replace("限定", "")]
    base = cands[-1]
    if base not in ("北海道",):
        cands.append(re.sub(r"[都府県]$", "", base))
    for k in cands:
        if k in AREA_POS:
            return (*AREA_POS[k], False)
    for k in sorted(AREA_POS, key=len, reverse=True):
        if k not in NO_SUBSTR and len(k) >= 2 and k in key:
            return (*AREA_POS[k], True)
    return (*REGION_POS.get(region, (36.0, 138.0)), True)


def merge(old, scraped, today):
    old_cats = old.get("cats", []) if old else []
    first_run = not old_cats
    by_id = {c["id"]: c for c in old_cats}
    result, used, added, name_count = [], set(), [], {}
    for region, area, name in scraped:
        # 同じ名前が別の地域にもある場合だけ、2件目以降に「@地域」を付けて区別する
        cid = name if name not in name_count else f"{name}@{area}"
        name_count[name] = name_count.get(name, 0) + 1
        lat, lng, approx = locate(area, name, region)
        region_name = region or "その他"
        if cid in by_id:
            c = dict(by_id[cid])
            c["area"], c["region"] = area, region_name
            if c.get("approx") and not approx:
                c["lat"], c["lng"], c["approx"] = lat, lng, False
        else:
            c = {"id": cid, "name": name, "area": area, "region": region_name,
                 "lat": lat, "lng": lng, "approx": approx,
                 "added": None if first_run else today}
            if not first_run:
                added.append(c)
        result.append(c)
        used.add(cid)
    for c in old_cats:  # 公式から消えたものも残す
        if c["id"] not in used:
            result.append(c)
    return result, added


def fetch():
    req = urllib.request.Request(URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", default="cats.json", help="出力する cats.json のパス")
    ap.add_argument("--html", help="埋め込みデータも更新する index.html のパス")
    ap.add_argument("--from-file", help="ネットに接続せず、保存したHTMLファイルから読む")
    ap.add_argument("--dry-run", action="store_true", help="ファイルに書かず結果だけ表示")
    ap.add_argument("--today", default=datetime.date.today().isoformat(), help=argparse.SUPPRESS)
    a = ap.parse_args()

    if a.from_file:
        text = open(a.from_file, encoding="utf-8").read()
    else:
        try:
            text = fetch()
        except Exception as e:  # noqa: BLE001
            print(f"取得に失敗しました: {e}", file=sys.stderr)
            return 1

    scraped = parse(text)
    if len(scraped) < MIN_EXPECTED:
        print(f"読み取れた件数が少なすぎます（{len(scraped)}件）。公式ページの構造が変わった可能性があるため、"
              "何も書き換えずに終了します。", file=sys.stderr)
        return 2

    try:
        old = json.load(open(a.json, encoding="utf-8"))
    except (OSError, ValueError):
        old = {}

    cats, added = merge(old, scraped, a.today)
    data = {"version": 1, "updated": a.today, "source": URL, "cats": cats}

    print(f"公式ページ: {len(scraped)}件 / cats.json: {len(cats)}件 / 新規: {len(added)}件")
    for c in added:
        flag = "（位置は目安）" if c["approx"] else ""
        print(f"  + 【{c['area']}】{c['name']}{flag}")
    if a.dry_run:
        return 0
    if old and old.get("cats") == cats:
        print("変更なし（ファイルは書き換えません）")
        return 0

    with open(a.json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")

    if a.html:
        src = open(a.html, encoding="utf-8").read()
        block = "/*CATS_START*/const EMBEDDED=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";/*CATS_END*/"
        new, n = re.subn(r"/\*CATS_START\*/.*?/\*CATS_END\*/", lambda m: block, src, flags=re.S)
        if n != 1:
            print("index.html に /*CATS_START*/ ... /*CATS_END*/ の目印が見つかりません。", file=sys.stderr)
            return 3
        open(a.html, "w", encoding="utf-8").write(new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
