from afr_pusher.message import format_batch_message, format_single_article_message


def test_format_batch_message_numbers_titles() -> None:
    message = format_batch_message(["  标题A  ", "", "标题B"])
    assert message == "1. 标题A；2. 标题B"


def test_format_single_article_message_contains_title_and_content() -> None:
    message = format_single_article_message(" 标题 ", " 正文内容 ")
    assert message == "标题：标题\n\n内容：正文内容"
