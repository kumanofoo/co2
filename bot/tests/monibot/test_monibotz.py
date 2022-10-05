import os
import pytest

@pytest.mark.skipif("os.environ.get('ZULIP_EMAIL') is None",
                    "os.environ.get('ZULIP_API_KEY') is None",
                    "os.environ.get('ZULIP_SITE') is None",
                    "os.environ.get('ZULIP_MONIBOT_STREAM') is None",
                    reason="Need environment variables of Zulip")
def test_parse_command():
    from monibot import monibotz
    parameter = [
        ("ip", "ip", ""),
        ("air 1d", "air", "1d"),
        ("", "help", ""),
        ("help", "help", ""),
        ("@**Bot** help", "help", ""),
        ("@**Bot** @**Dot** help", "help", ""),
        ("?", "?", ""),
        ("hello world", "book", "hello world"),
        ("    hello world", "book", "hello world"),
        ("book hello world", "book", "hello world"),
        ("@**Bot** book hello world", "book", "hello world"),
        ("@**Bot** @**Dot** book hello world", "book", "hello world"),
    ]
    for message, command, argument in parameter:
        (cmd, arg) = monibotz.parse_command(message)
        assert cmd == command
        assert arg == argument
