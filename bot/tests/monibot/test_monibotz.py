from monibot import monibotz


def test_parse_command():
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
