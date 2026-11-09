import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app as app_module  # noqa: E402

SAMPLE = {
    "article_title": "テスト記事のタイトル",
    "article_url": "https://example-blog.jp/entry/123",
    "blog_url": "https://example-blog.jp/",
    "blog_name": "example-blog.jp",
}

FIXTURE_HTML = """
<div class="blog-detail">
  <div class="title">
    <a target="_blank" href="https://link.blogmura.com/out/?ch=111&amp;url=https%3A%2F%2Fgoodend.xyz%2F">グッドエンド日記</a>
  </div>
  <ul class="post-list">
    <li><a href="https://link.blogmura.com/out/?ch=111&amp;item=222&amp;url=https%3A%2F%2Fgoodend.xyz%2Farchives%2F82189" target="_blank">
    <span class="date">2日前</span>    良い終わり方について</a></li>
    <li><a href="https://link.blogmura.com/out/?ch=111&amp;item=223&amp;url=https%3A%2F%2Fgoodend.xyz%2Farchives%2F82180" target="_blank">
    <span class="date">3日前</span>    前の記事</a></li>
  </ul>
  <div class="title">
    <a target="_blank" href="https://link.blogmura.com/out/?ch=333&amp;url=https%3A%2F%2Ftakarazuka.blog%2F">宝塚メモ</a>
  </div>
  <ul class="post-list">
    <li><a href="https://link.blogmura.com/out/?ch=333&amp;item=444&amp;url=https%3A%2F%2Ftakarazuka.blog%2F2026%2F11%2F08%2Fhoshosora%2F" target="_blank">
    <span class="date">昨日</span>    星空の感想</a></li>
  </ul>
  <a href="https://blogmura.com/feature-post" class="content-subtitle-link">特集</a>
</div>
"""


class ParseRankingTest(unittest.TestCase):
    def test_parse_entries(self):
        entries = app_module.parse_ranking(FIXTURE_HTML)
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0]["article_url"],
                         "https://goodend.xyz/archives/82189")
        self.assertEqual(entries[0]["blog_url"], "https://goodend.xyz/")
        self.assertEqual(entries[0]["blog_name"], "グッドエンド日記")
        self.assertEqual(entries[0]["article_title"], "良い終わり方について")
        self.assertEqual(entries[2]["article_title"], "星空の感想")
        self.assertEqual(entries[2]["blog_name"], "宝塚メモ")

    def test_parse_empty(self):
        self.assertEqual(app_module.parse_ranking("<html></html>"), [])


class RandomSiteBlogTest(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()
        self._orig_fetch = app_module.fetch_random_entry

    def tearDown(self):
        app_module.fetch_random_entry = self._orig_fetch

    def test_healthz(self):
        res = self.client.get("/healthz")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["status"], "ok")

    def test_index_ok(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        body = res.get_data(as_text=True)
        self.assertIn("ランダム個人ブログ", body)
        self.assertIn("ランダムで記事を表示", body)

    def test_random_success(self):
        app_module.fetch_random_entry = lambda: dict(SAMPLE)
        res = self.client.get("/random")
        self.assertEqual(res.status_code, 200)
        body = res.get_data(as_text=True)
        self.assertIn("テスト記事のタイトル", body)
        self.assertIn("example-blog.jp", body)
        self.assertIn("https://example-blog.jp/entry/123", body)
        self.assertIn("記事を読む", body)

    def test_random_failure_shows_error(self):
        def boom():
            raise RuntimeError("network down")

        app_module.fetch_random_entry = boom
        res = self.client.get("/random")
        self.assertEqual(res.status_code, 200)
        body = res.get_data(as_text=True)
        self.assertIn("記事を取得できませんでした", body)


class FallbackTest(unittest.TestCase):
    def test_seed_fallback_on_fetch_error(self):
        orig = app_module.fetch_entries

        def boom():
            raise RuntimeError("network down")

        try:
            app_module.fetch_entries = boom
            entry = app_module.fetch_random_entry()
        finally:
            app_module.fetch_entries = orig
        self.assertIn(entry, app_module.SEED_BLOGS)


if __name__ == "__main__":
    unittest.main()
