from monibot.ping import ICMP, DNS, Web


def test_icmp():
    parameters = [
        ("localhost", True, "min/avg/max/"),
        ("192.0.2.1", False, "192.0.2.1: unreachable"),
        ("example.invalid", False, "example.invalid: failure in name resolution"),
    ]

    for host, expected_alive, expected_res in parameters:
        icmp_alive = ICMP(host)
        alive, res = icmp_alive.is_alive()
        assert alive is expected_alive, f"{host}: {alive} vs {expected_alive}"
        assert expected_res in res, f"{host}: {res} vs {expected_res}"


def test_dns():
    dns_alive = DNS(nameserver="192.0.2.1", hostname="example.com")
    alive, res = dns_alive.is_alive()
    assert alive is False
    assert res == "Request Timeout", f"{res}"

    parameters = [
        ("www.example.com", True, "23.204.139.205"),
        ("www.example.invalid", False, "Hostname does not exist"),
        ("xyz", False, "No records"),
    ]
    for host, expected_alive, expected_res in parameters:
        dns_alive = DNS(hostname=host)
        alive, res = dns_alive.is_alive()
        assert alive is expected_alive, f"{host}: {alive} vs {expected_alive}"
        assert res == expected_res, f"{host}: {res} vs {expected_res}"


def test_web():
    parameters = [
        ("http://www.example.com", True, "200"),
        ("http://www.example.invalid", False, "Failed to establish a new connection"),
        ("https://httpstat.us/200?sleep=10000", False, "Timeout"),
    ]
    for url, expected_alive, expected_res in parameters:
        web_alive = Web(url)
        alive, res = web_alive.is_alive()
        assert alive is expected_alive, f"{url}: {alive} vs {expected_alive}"
        assert res == expected_res, f"{url}: {res} vs {expected_res}"
