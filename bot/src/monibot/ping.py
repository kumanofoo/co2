from typing import Tuple
from abc import ABC, abstractmethod
import subprocess
import requests
import dns.flags
import dns.rdatatype
import dns.resolver
import re
import logging
log = logging.getLogger(__name__)


class Ping(ABC):
    @abstractmethod
    def is_alive(self) -> Tuple[bool, str]:
        pass

    @property
    @abstractmethod
    def target(self) -> str:
        pass


class ICMP(Ping):
    def __init__(self, hostname: str):
        self.hostname = hostname

    def is_alive(self) -> Tuple[bool, str]:
        command = subprocess.Popen(
            ["ping", "-c", "5", "-q", self.hostname],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        res, err = command.communicate()
        if command.returncode == 0:
            response = res.decode("utf-8").split("\n")[-2]
            alive = True
        elif command.returncode == 1:
            response = f"{self.target}: unreachable"
            alive = False
        else:
            response = f"{self.target}: failure in name resolution"
            alive = False
        return alive, response

    @property
    def target(self) -> str:
        return self.hostname


class Web(Ping):
    def __init__(self, url: str, timeout_sec: float = 3.0):
        self.url = url
        self.timeout = timeout_sec

    def is_alive(self) -> Tuple[bool, str]:
        response = self.get_status()
        if response == 200:
            alive = True
        else:
            alive = False
        return alive, str(response)

    def get_status(self) -> int:
        status_code = -1
        try:
            response = requests.get(self.url, timeout=self.timeout)
        except requests.exceptions.ConnectionError:
            status_code = "Failed to establish a new connection"
        except requests.exceptions.Timeout:
            status_code = "Timeout"
        else:
            status_code = response.status_code
        return status_code

    @property
    def target(self) -> str:
        return self.url


class DNS(Ping):
    def __init__(self, hostname: str, nameserver: str = '8.8.8.8'):
        self.resolver = dns.resolver.Resolver()
        self.resolver.nameservers = [nameserver]
        self.resolver.timeout = 3.0
        self.resolver.lifetime = 5.0
        self.hostname = hostname
        self.re_addr = re.compile(
            r'^(?:(?:[1-9]?\d|1\d\d|2[0-4]\d|25[0-5])\.){3}'
            r'(?:[1-9]?\d|1\d\d|2[0-4]\d|25[0-5])$')

    def is_alive(self) -> Tuple[bool, str]:
        answer = self.lookup()
        if self.re_addr.search(answer):
            alive = True
        else:
            alive = False
        return alive, answer

    def lookup(self) -> str:
        answer = 'None'
        try:
            answers = self.resolver.resolve(
                self.hostname,
                raise_on_no_answer=False)
        except dns.resolver.NoNameservers:
            answer = "No response to dns request"
        except dns.resolver.NXDOMAIN:
            answer = "Hostname does not exist"
        except dns.resolver.Timeout:
            answer = "Request Timeout"
        except dns.resolver.NoAnswer:
            answer = "No answer"
        else:
            if len(answers) < 1:
                answer = "No records"
            else:
                answer = str(answers[0])
        return answer

    @property
    def target(self) -> str:
        return self.hostname


def test_icmp():
    parameters = [
        ("localhost", True, "min/avg/max/"),
        ("192.0.2.1", False, "192.0.2.1: unreachable"),
        ("example.invalid", False,
         "example.invalid: failure in name resolution"),
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
        ("www.example.com", True, '93.184.216.34'),
        ("www.example.invalid", False,
         "Hostname does not exist"),
        ("xyz", False, "No records"),
    ]
    for host, expected_alive, expected_res in parameters:
        dns_alive = DNS(hostname=host)
        alive, res = dns_alive.is_alive()
        assert alive is expected_alive, f"{host}: {alive} vs {expected_alive}"
        assert res == expected_res, f"{host}: {res} vs {expected_res}"


def test_web():
    parameters = [
        ("http://www.example.com", True, '200'),
        ("http://www.example.invalid", False,
         "Failed to establish a new connection"),
        ("https://httpstat.us/200?sleep=10000", False, "Timeout"),
    ]
    for url, expected_alive, expected_res in parameters:
        web_alive = Web(url)
        alive, res = web_alive.is_alive()
        assert alive is expected_alive, f"{url}: {alive} vs {expected_alive}"
        assert res == expected_res, f"{url}: {res} vs {expected_res}"


if __name__ == "__main__":
    test_icmp()
    test_dns()
    test_web()
