from bs4 import BeautifulSoup

from afr_pusher.fetchers.afr import AFRFetcher


def test_extract_article_urls_filters_and_dedupes() -> None:
    html = """
    <html><body>
      <a href="/companies/banking/article-one-20260207-pabc123">A</a>
      <a href="https://www.afr.com/companies/banking/article-one-20260207-pabc123">A2</a>
      <a href="/markets/market-two-20260101-pdef456/">B</a>
      <a href="/not-an-article">No</a>
      <a href="https://example.com/x-20260101-paaa111">External</a>
    </body></html>
    """

    fetcher = AFRFetcher(
        homepage_url="https://www.afr.com",
        timeout_sec=5,
        user_agent="ua",
    )

    urls = fetcher._extract_article_urls(html)

    assert urls == [
        "https://www.afr.com/companies/banking/article-one-20260207-pabc123",
        "https://www.afr.com/markets/market-two-20260101-pdef456",
    ]


def test_extract_article_urls_respects_path_prefix_filter() -> None:
    html = """
    <html><body>
      <a href="/markets/equity-markets/a-20260207-paaa111">A</a>
      <a href="/companies/banking/b-20260207-pbbb222">B</a>
      <a href="/markets/equity-markets/c-20260207-pccc333">C</a>
    </body></html>
    """

    fetcher = AFRFetcher(
        homepage_url="https://www.afr.com/topic/markets-live-1po",
        timeout_sec=5,
        user_agent="ua",
        article_path_prefix="/markets/equity-markets/",
    )

    urls = fetcher._extract_article_urls(html)

    assert urls == [
        "https://www.afr.com/markets/equity-markets/a-20260207-paaa111",
        "https://www.afr.com/markets/equity-markets/c-20260207-pccc333",
    ]


def test_extract_article_content_from_liveblog_ld_json() -> None:
    fetcher = AFRFetcher(homepage_url="https://www.afr.com", timeout_sec=5, user_agent="ua")
    soup = BeautifulSoup("<html></html>", "html.parser")

    ld_json = {
        "@type": "LiveBlogPosting",
        "articleBody": "Lead <b>content</b> paragraph with enough detail for testing.",
        "liveBlogUpdate": [
            {"@type": "BlogPosting", "articleBody": "Another update paragraph with more context and details."},
            {"@type": "BlogPosting", "articleBody": "short"},
        ],
    }

    content = fetcher._extract_article_content(soup, ld_json)
    assert content is not None
    assert "Lead content paragraph with enough detail for testing." in content
    assert "Another update paragraph with more context and details." in content
    assert "short" not in content


def test_extract_article_content_falls_back_to_dom_paragraphs() -> None:
    fetcher = AFRFetcher(homepage_url="https://www.afr.com", timeout_sec=5, user_agent="ua")
    soup = BeautifulSoup(
        """
        <html><body>
          <article>
            <p>Short title line</p>
            <p>This is a longer article paragraph that should be included in extracted body content.</p>
            <p>Another detailed paragraph that should also be included because it is long enough.</p>
          </article>
        </body></html>
        """,
        "html.parser",
    )

    content = fetcher._extract_article_content(soup, {})
    assert content is not None
    assert "This is a longer article paragraph" in content
    assert "Another detailed paragraph" in content


def test_fetch_article_prefers_content_api_when_enabled(monkeypatch) -> None:
    fetcher = AFRFetcher(
        homepage_url="https://www.afr.com/street-talk",
        timeout_sec=5,
        user_agent="ua",
        article_path_prefix="/street-talk",
        prefer_content_api=True,
    )
    article_url = "https://www.afr.com/street-talk/example-20260207-pabc123"
    page_html = """
    <html>
      <head>
        <meta property="og:title" content="Street Talk Example">
        <meta name="description" content="Short summary">
        <meta property="article:published_time" content="2026-02-07T00:00:00Z">
      </head>
      <body>
        <article>
          <p>Short page teaser.</p>
        </article>
      </body>
    </html>
    """

    monkeypatch.setattr(fetcher, "_get_text", lambda url: page_html)
    monkeypatch.setattr(
        fetcher,
        "_get_json",
        lambda url: {
            "asset": {
                "body": (
                    "<p>API lead paragraph with enough detail for testing.</p>"
                    "<p>API second paragraph that should win over the sparse page teaser.</p>"
                )
            }
        },
    )

    article = fetcher._fetch_article(article_url)

    assert article is not None
    assert article.content is not None
    assert "API lead paragraph with enough detail for testing." in article.content
    assert "API second paragraph that should win over the sparse page teaser." in article.content
    assert "Short page teaser." not in article.content


def test_fetch_article_falls_back_to_page_content_when_api_has_no_body(monkeypatch) -> None:
    fetcher = AFRFetcher(
        homepage_url="https://www.afr.com/street-talk",
        timeout_sec=5,
        user_agent="ua",
        article_path_prefix="/street-talk",
        prefer_content_api=True,
    )
    article_url = "https://www.afr.com/street-talk/example-20260207-pabc123"
    page_html = """
    <html>
      <head>
        <meta property="og:title" content="Street Talk Example">
        <meta name="description" content="Short summary">
        <meta property="article:published_time" content="2026-02-07T00:00:00Z">
      </head>
      <body>
        <article>
          <p>This is a longer fallback paragraph that should still be extracted when the API is unavailable.</p>
          <p>Another detailed fallback paragraph that keeps the old HTML-based behaviour intact.</p>
        </article>
      </body>
    </html>
    """

    monkeypatch.setattr(fetcher, "_get_text", lambda url: page_html)
    monkeypatch.setattr(fetcher, "_get_json", lambda url: {"asset": {}})

    article = fetcher._fetch_article(article_url)

    assert article is not None
    assert article.content is not None
    assert "longer fallback paragraph" in article.content
    assert "old HTML-based behaviour intact" in article.content
