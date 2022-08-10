#!/usr/bin/env python3

import time
import re
import os
import json
import random
from typing import Dict
import requests
from requests_html import HTMLSession

import logging
log = logging.getLogger(__name__)

ZEN = "".join(chr(0xff01 + i) for i in range(94))
HAN = "".join(chr(0x21 + i) for i in range(94))
ZEN2HAN = str.maketrans(ZEN, HAN)


class BookStatusError(Exception):
    pass


class BookStatus:
    """
    check book's status in libraries
    """
    def __init__(self):
        self.CALIL_APPKEY = os.environ.get("CALIL_APPKEY")
        if not self.CALIL_APPKEY:
            raise BookStatusError("no 'CALIL_APPKEY' in environment variables")

        self.BOOK_CONFIG = os.environ.get("BOOK_CONFIG")
        if not self.BOOK_CONFIG:
            raise BookStatusError("no 'BOOK_CONFIG' in environment variables")

        try:
            f = open(self.BOOK_CONFIG, encoding='utf-8')
        except IOError:
            raise BookStatusError(
                "cannot open configuration file '{0}'".format(
                    self.BOOK_CONFIG))

        try:
            conf = json.load(f)
        except Exception as e:
            log.warning(e)
            raise BookStatusError("cannot parse configuration")

        self.configuration = conf.get('book', None)
        if not self.configuration:
            raise BookStatusError("'book' key not found in %s"
                                  % self.BOOK_CONFIG)

        self.libraries = self.configuration.keys()
        if len(self.libraries) == 0:
            raise BookStatusError("library not found in %s"
                                  % self.BOOK_CONFIG)
        log.debug('libraries: %s' % self.libraries)

    def normalize_isbn(self, text: str) -> str:
        text_no_hyphen = text.strip().replace('-', '')
        isbn10 = re.compile(r"^\d{9}[0-9X]$")
        isbn13 = re.compile(r"^\d{13}$")

        if isbn10.match(text_no_hyphen):
            return text_no_hyphen
        if isbn13.match(text_no_hyphen):
            return text_no_hyphen

        return ""

    def get_isbn_c(self, book: str, max_count: int = 5) -> Dict[str, str]:
        log.debug('get_isbn_c(%s, %d)' % (book, max_count))
        url = 'https://calil.jp/search'
        params = {
            'q': book
        }
        isbns = {}
        session = HTMLSession()
        try:
            res = session.get(url, params=params)
        except Exception as e:
            log.warning(e)
            return None
        else:
            if res.status_code != 200:
                log.warning('%s return %d' % (url, res.status_code))
                return None

        title = res.html.find('a.title')
        book_han = book.translate(ZEN2HAN).lower().split()
        for t in title:
            log.debug(f"{t.text}")
            t_han = t.text.translate(ZEN2HAN).lower().split()
            t_han.append('')  # sentinel
            match = True
            query_isbn = self.normalize_isbn(book.translate(ZEN2HAN))
            if query_isbn == "":  # not ISBN code
                for b in book_han:
                    if t_han.pop(0) != b:
                        match = False
                        break
            if match:
                for link in t.links:
                    try:
                        isbn = self.normalize_isbn(link.split('/')[2])
                    except ValueError:
                        continue
                    if isbn:
                        isbns[isbn] = t.text.translate(ZEN2HAN)
        return isbns

    def get_isbn_h(self, book: str, max_count: int = 5) -> Dict[str, str]:
        log.debug('get_isbn_h((%s, %d)' % (book, max_count))
        base_url = "https://honto.jp/netstore/search_10"
        url = f"{base_url}{book}.html"
        params = {
            'srchf': 1,
            'tbty': 1,
        }
        isbns = {}
        book_link = []
        session = HTMLSession()
        try:
            res = session.get(url, params=params)
        except Exception as e:
            log.warning(e)
            return None
        else:
            if res.status_code != 200:
                log.warning('%s return %d' % (url, res.status_code))
                return None

        title = res.html.find('a.dyTitle')
        book_han = book.translate(ZEN2HAN).lower().split()
        for t in title:
            log.debug(f"{t.text}")
            t_han = t.text.translate(ZEN2HAN).lower().split()
            t_han.append('')  # sentinel
            match = True
            query_isbn = self.normalize_isbn(book.translate(ZEN2HAN))
            if query_isbn == "":  # not ISBN code
                for b in book_han:
                    if t_han.pop(0) != b:
                        match = False
                        break
            if match:
                for link in t.links:
                    book_link.append((t.text.translate(ZEN2HAN), link))

        for title, link in book_link[:max_count]:
            try:
                res = session.get(link)
            except Exception as e:
                log.warning(e)
                return None
            else:
                if res.status_code != 200:
                    log.warning('%s return %d' % (link, res.status_code))
                    return None

            uls = res.html.find('ul.stItemData')
            for ul in uls:
                for li in ul.find('li'):
                    try:
                        label, isbn = li.text.split('：')
                    except ValueError:
                        continue
                    result = self.normalize_isbn(isbn)
                    if result:
                        isbns[result] = title

        log.debug('get_isbn_h(): %s' % isbns)
        return isbns

    def get_book_status(self, isbns, systemids, timeout=60):
        log.debug('get_book_status(%s, %s, %s)' %
                  (isbns, systemids, timeout))

        polling_interval = 2  # [sec]
        url = 'https://api.calil.jp/check'
        params = {
            'appkey': self.CALIL_APPKEY,
            'callback': 'no'
        }
        params['isbn'] = ','.join(isbns.keys())
        params['systemid'] = ','.join(systemids)

        try:
            res = requests.get(url, params=params)
        except Exception as e:
            log.warning(e)
            return []

        if res.status_code != 200:
            log.warning('%s return %d' % (url, res.status_code))
            return []

        json_data = res.json()
        timer = timeout/polling_interval
        while json_data['continue'] == 1:
            if timer <= 0:
                log.warning('calil.jp query time-out')
                return []
            timer -= 1
            time.sleep(polling_interval)
            try:
                params = {
                    'appkey': self.CALIL_APPKEY,
                    'session': json_data['session'],
                    'callback': 'no'
                }
                res = requests.get(url, params=params)
            except Exception as e:
                log.warning(e)
                return []
            else:
                if res.status_code != 200:
                    log.warning('%s return %d' % (url, res.status_code))
                    return []
                else:
                    json_data = res.json()

        log.debug('get_book_status(): %s' % json_data)
        return json_data

    def search(self, book):
        log.debug('search(%s)' % book)
        result = {'book': book, 'data': {}}

        isbns = self.get_isbn_h(book)
        if not isbns:
            isbns = self.get_isbn_c(book)
        if not isbns:
            return (result, self.result_by_string(result))

        book_status = self.get_book_status(isbns, self.libraries)
        if not book_status:
            return (result, 'Search error :construction:')

        for isbn in book_status['books']:
            title = isbns[isbn]
            result['data'][title] = {}
            for systemid in book_status['books'][isbn]:
                result['data'][title][systemid] = {}
                library = result['data'][title][systemid]
                status = book_status['books'][isbn][systemid]
                library['name'] = self.configuration[systemid]
                if status['status'] == 'OK' or status['status'] == 'Cache':
                    library['url'] = status['reserveurl']
                    library['status'] = status['libkey']
                else:
                    library['url'] = 'https://httpbin.org/status/418'
                    library['status'] = {' -_-': 'Error'}

        log.debug('search(): %s' % result)
        return (result, self.result_by_string(result))

    def result_by_string(self, result):
        if not result:
            return None

        if not result['data']:
            emoji = [
                ':collision:',
                ':moyai:',
                ':socks:',
                ':ramen:',
                ':jack_o_lantern:'
            ]
            return emoji[random.randrange(0, len(emoji))]

        string = '[%s]\n' % result['book']
        for title in result['data']:
            string += '\n%s\n' % title
            for systemid in result['data'][title]:
                library = result['data'][title][systemid]
                if library['status']:
                    for place in library['status']:
                        string += '- %s(%s): <%s|%s>\n' % (
                            library['name'], place,
                            library['url'], library['status'][place])
                else:
                    string += '- %s: 蔵書なし\n' % (library['name'])

        return string


"""
{
  "book": <book>,
  "data": {
    <title>: {
      <systemid>: {
        "name": <library name>,
        "url": <url>,
        "status": {<place>:<status>, <place>:<status>, ...}
      },
      <systemid>: {
        "name": <library name>,
        "url": <url>,
        "status": {<place>:<status>, <place>:<status>, ...}
      },
      ...
    },
    <title>: {
      <systemid>: {
        "name": <library name>,
        "url": <url>,
        "status": {<place>:<status>, <place>:<status>}
      },
      ...
    },
    ...
  }
}

"""


if __name__ == '__main__':
    """
    for debug
    """
    log_level = logging.DEBUG
    formatter = '%(asctime)s %(name)s[%(lineno)s] %(levelname)s: %(message)s'
    logging.basicConfig(level=log_level, format=formatter)

    """
    michi: hankaku zenkaku
    星界の報告: not owned
    Twiter: ISBN not found
    ナポレオン: many title
    リーダブルコード: one title
    インターネットを256倍使うための本: a few title
    誰が音楽をタダにした？: with a special character
    """
    books = ['michi', '星界の報告', 'Twiter']
    # books = ['ナポレオン', 'リーダブルコード', 'インターネットを256倍使うための本', '誰が音楽をタダにした？']

    bs = BookStatus()
    for book in books:
        res = bs.search(book)
        print('----')
        print(res[0])
        print('----')
        print(res[1])
        print('----')
