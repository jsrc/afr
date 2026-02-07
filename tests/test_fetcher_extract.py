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
