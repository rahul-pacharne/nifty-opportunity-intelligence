import json
from io import BytesIO
from urllib.error import HTTPError

from app.notifications.telegram_api import send_message


class _Response:
    def __init__(self, body: str) -> None:
        self._body = body.encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None


def test_send_message_posts_to_the_bot_api() -> None:
    captured = {}

    def opener(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = request.data.decode()
        captured["timeout"] = timeout
        return _Response(json.dumps({"ok": True, "result": {"message_id": 1}}))

    result = send_message("123456:secret", "999", "hello", opener=opener)
    assert result["ok"] is True
    assert captured["url"] == "https://api.telegram.org/bot123456:secret/sendMessage"
    assert "chat_id=999" in captured["body"]
    assert "hello" in captured["body"]


def test_rejected_token_does_not_include_the_secret() -> None:
    def opener(request, timeout):
        raise HTTPError(request.full_url, 404, "Not Found", hdrs=None, fp=BytesIO(b'{"ok":false,"description":"Not Found"}'))

    try:
        send_message("123456:secret", "999", "hello", opener=opener)
    except RuntimeError as exc:
        assert "secret" not in str(exc)
        assert "Not Found" in str(exc)
    else:
        raise AssertionError("expected a runtime error")
