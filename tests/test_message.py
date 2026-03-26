from afr_pusher.message import format_batch_message, format_single_article_message, parse_content_blocks
from afr_pusher.models import ArticleBlock


def test_format_batch_message_renders_html_links() -> None:
    message = format_batch_message(
        ["  标题A  ", "", "标题B"],
        article_urls=["https://example.com/a", None, "https://example.com/b"],
    )
    assert message == (
        "<b>AFR 要闻速览</b>\n\n"
        '1. <a href="https://example.com/a">标题A</a>\n'
        "2. 标题B"
    )


def test_format_single_article_message_contains_title_and_blocks() -> None:
    message = format_single_article_message(
        " 标题 ",
        " 正文内容 ",
        article_url="https://example.com/a",
        content_blocks=(
            ArticleBlock(kind="paragraph", text="正文内容"),
            ArticleBlock(kind="list_item", text="要点"),
        ),
    )
    assert message == (
        '<a href="https://example.com/a"><b>标题</b></a>\n\n'
        "正文内容\n\n"
        "• 要点"
    )


def test_parse_content_blocks_detects_list_items() -> None:
    blocks = parse_content_blocks("第一段\n\n• 要点一\n\n- 要点二")
    assert blocks == (
        ArticleBlock(kind="paragraph", text="第一段"),
        ArticleBlock(kind="list_item", text="要点一"),
        ArticleBlock(kind="list_item", text="要点二"),
    )
