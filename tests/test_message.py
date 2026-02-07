from afr_pusher.message import format_batch_message


def test_format_batch_message_numbers_titles() -> None:
    message = format_batch_message(["  标题A  ", "", "标题B"])
    assert message == "1. 标题A；2. 标题B"
