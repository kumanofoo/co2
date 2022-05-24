#!/usr/bin/env python3

import os
import json
import requests
import time

import logging
log = logging.getLogger(__name__)


class GetIPError(Exception):
    pass


class GetIP:
    def __init__(self):
        log.debug("__init__()")

        self.GETIP_CONFIG = os.environ.get("GETIP_CONFIG")
        if not self.GETIP_CONFIG:
            raise GetIPError("no 'GETIP_CONFIG' in environment variables")

        try:
            f = open(self.GETIP_CONFIG)
        except IOError:
            raise GetIPError(
                "cannot open configuration file '{0}'".format(
                    self.GETIP_CONFIG))

        try:
            conf = json.load(f)
        except ValueError as e:
            log.warning(e)
            raise GetIPError("cannot parse configuration")

        self.configuration = conf.get('getip', None)
        if not self.configuration:
            raise GetIPError("'getip' key not found in %s"
                             % self.GETIP_CONFIG)

        self.urls = self.configuration.get('urls', None)
        if not self.urls:
            raise GetIPError("'urls' not found")
        if type(self.urls) is not list:
            raise GetIPError("'urls' is not 'list'")
        log.debug('urls: %s' % self.urls)

        self.current_url = 0
        self.url = self.urls[self.current_url]

    def get(self):
        log.debug("get()")
        ip = None
        for i in range(len(self.urls)):
            self.current_url = (self.current_url + 1) % len(self.urls)
            try:
                url = self.urls[self.current_url]
                res = requests.get(url)
            except Exception as e:
                log.warning(e)
            else:
                if res.status_code == 200:
                    ip = res.text
                    break
                else:
                    log.warning('%s return %d' % (url, res.status_code))

        log.debug("exit get(): %s" % ip)
        return ip


if __name__ == '__main__':
    log_level = logging.DEBUG
    formatter = '%(asctime)s %(name)s[%(lineno)s] %(levelname)s: %(message)s'
    logging.basicConfig(level=log_level, format=formatter)

    ip = GetIP()
    for i in range(5):
        print(ip.get())
        time.sleep(5)
