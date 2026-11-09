"""ランダム個人サイト・ブログ（randomsiteblog）

ボタンを押すと、個人サイト・個人ブログの記事をランダムで1件表示する
ツール。randomwikipedia の個人サイト／ブログ版。記事の候補は
「にほんブログ村」の総合ランキング（公開ページ）からサーバー側で
取得し、その中から1件を選ぶ。取得できない場合は、長く続いている
著名な個人サイトのシードリストから選ぶ。単一ファイル Flask。
"""
import html
import os
import random
import re
import time
import urllib.parse
import urllib.request

from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

RANKING_URL = "https://blogmura.com/ranking/in"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
FETCH_TIMEOUT = 20
CACHE_SECONDS = 600

# 取得に失敗したときの予備（長く続いている著名な個人サイト）
SEED_BLOGS = [
    {"article_title": "結城浩のホームページ",
     "article_url": "https://www.hyuki.com/",
     "blog_url": "https://www.hyuki.com/", "blog_name": "www.hyuki.com"},
    {"article_title": "高木浩光＠自宅の日記",
     "article_url": "https://takagi-hiromitsu.jp/diary/",
     "blog_url": "https://takagi-hiromitsu.jp/",
     "blog_name": "takagi-hiromitsu.jp"},
    {"article_title": "増井俊之のホームページ",
     "article_url": "https://www.pitecan.com/",
     "blog_url": "https://www.pitecan.com/", "blog_name": "www.pitecan.com"},
]

_cache = {"at": 0.0, "entries": []}

_OUT_LINK_RE = re.compile(
    r'<a[^>]+href="(https://link\.blogmura\.com/out/\?[^"]+)"[^>]*>(.*?)</a>',
    re.DOTALL,
)
_DATE_SPAN_RE = re.compile(r'<span class="date">.*?</span>', re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(raw):
    return html.unescape(_TAG_RE.sub("", raw)).strip()


def parse_ranking(html_text):
    """ブログ村ランキングのHTMLから記事エントリのリストを作る。

    ランキングの各ブログには、ブログ本体へのリンク（ch のみ）と
    最新記事へのリンク（ch + item）が並ぶ。item 付きを記事として拾い、
    ch が一致するブログ本体リンクからブログ名とURLを補う。
    """
    blogs = {}
    articles = []
    for href, raw_inner in _OUT_LINK_RE.findall(html_text):
        href = html.unescape(href)
        query = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
        urls = query.get("url") or []
        chs = query.get("ch") or []
        if not urls or not chs:
            continue
        target = urls[0]
        parts = urllib.parse.urlparse(target)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            continue
        if "item" in query:
            title = _clean_text(_DATE_SPAN_RE.sub("", raw_inner))
            articles.append((chs[0], title, target, parts))
        else:
            name = _clean_text(raw_inner)
            if name:
                blogs[chs[0]] = (name, target)
    entries = []
    seen = set()
    for ch, title, article_url, parts in articles:
        if article_url in seen:
            continue
        seen.add(article_url)
        blog_name, blog_url = blogs.get(
            ch, (parts.netloc, "%s://%s/" % (parts.scheme, parts.netloc))
        )
        entries.append({
            "article_title": title or blog_name,
            "article_url": article_url,
            "blog_url": blog_url,
            "blog_name": blog_name,
        })
    return entries


def fetch_entries():
    """ランキングから記事候補を取得する（10分キャッシュ）。"""
    now = time.time()
    if _cache["entries"] and now - _cache["at"] < CACHE_SECONDS:
        return _cache["entries"]
    req = urllib.request.Request(
        RANKING_URL, headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as res:
        text = res.read().decode("utf-8", "replace")
    entries = parse_ranking(text)
    if not entries:
        raise ValueError("no entries parsed")
    _cache["entries"] = entries
    _cache["at"] = now
    return entries


def fetch_random_entry():
    """ランダムな記事を1件返す。取得失敗時はシードから選ぶ。"""
    try:
        entries = fetch_entries()
    except Exception:
        entries = SEED_BLOGS
    return random.choice(entries)


PAGE = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ランダム個人ブログ</title>
<style>
body{font-family:sans-serif;max-width:680px;margin:2em auto;padding:0 1em;color:#222}
h1{font-size:1.5em}
.bigbtn{display:inline-block;font-size:1.15em;padding:.7em 1.6em;margin:.6em 0;
background:#e07b39;color:#fff;border:none;border-radius:8px;cursor:pointer}
.bigbtn:hover{background:#c4642a}
.card{border:1px solid #ccc;border-radius:10px;padding:1em 1.2em;margin-top:1em}
.blog{color:#555;font-size:.95em;margin:.2em 0 .6em}
.error{border:1px solid #d66;background:#fff3f3;border-radius:10px;padding:1em 1.2em;margin-top:1em}
a.read{font-weight:bold}
footer{margin-top:2em;color:#777;font-size:.85em}
</style>
</head><body>
<h1>🏠 ランダム個人ブログ</h1>
<p>ボタンを押すと、個人サイト・個人ブログの記事をランダムで1件表示します。知らないブログとの出会いをどうぞ。</p>
<form method="get" action="/random">
  <button type="submit" class="bigbtn">🎲 ランダムで記事を表示</button>
</form>
{% if entry %}
<div class="card">
  <h2>{{ entry.article_title }}</h2>
  <p class="blog">ブログ：{{ entry.blog_name }}</p>
  <p><a class="read" href="{{ entry.article_url }}" target="_blank" rel="noopener">記事を読む →</a></p>
  <p><a href="{{ entry.blog_url }}" target="_blank" rel="noopener">ブログのトップへ</a></p>
</div>
{% elif error %}
<div class="error">
  <p>⚠️ {{ error }}</p>
  <p>通信がうまくいかなかったようです。もう一度ボタンを押してみてください。</p>
</div>
{% endif %}
<footer>記事の候補：<a href="https://blogmura.com/" target="_blank" rel="noopener">にほんブログ村</a>の総合ランキングから取得しています。</footer>
</body></html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE, entry=None, error=None)


@app.route("/random")
def random_entry():
    try:
        entry = fetch_random_entry()
    except Exception:
        return render_template_string(
            PAGE, entry=None, error="記事を取得できませんでした。"
        )
    return render_template_string(PAGE, entry=entry, error=None)


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
