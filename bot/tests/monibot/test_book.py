#!/usr/bin/env python3

import time
import os
import re
import json
import pytest
import monibot.book as book

os.environ['BOOK_CONFIG'] = 'book_config_dummy'
os.environ['CALIL_APPKEY'] = 'calil_appkey_dummy'
book_config = os.environ['BOOK_CONFIG']
calil_appkey = os.environ['CALIL_APPKEY']
testdir = 'tests/monibot'


def requests_mock(*args, **kwargs):
    prefix = f'{testdir}/test_book_response_mock/'
    mockfiles = {
        'Twiter': 'twiter-search.html',
        'イマココ': 'imakoko-search.html'
    }
    time.sleep(1)

    class MockResponse:
        def __init__(self, text, status_code):
            self.status_code = status_code
            self.text = text

        def json(self):
            return json.loads(self.text)

    if args[0].startswith('https://honto.jp/netstore/search.html'):
        mockfile = mockfiles[kwargs['params']['k']]
        try:
            f = open(prefix + mockfile, encoding='utf-8')
        except IOError as e:
            print(e)
            raise(e)
        return MockResponse(f.read(), 200)

    if args[0].startswith('https://honto.jp/netstore/pd-book'):
        mockfile = args[0].split('/')[-1]
        try:
            f = open(prefix + mockfile, encoding='utf-8')
        except IOError as e:
            print(e)
            raise(e)
        return MockResponse(f.read(), 200)

    if args[0].startswith('https://api.calil.jp/check'):
        isbn = sorted(kwargs['params']['isbn'].split(','))[0]
        mockfile = '%s.html' % (isbn)
        try:
            f = open(prefix + mockfile, encoding='utf-8')
        except IOError as e:
            print(e)
            raise(e)
        return MockResponse(f.read(), 200)

    return MockResponse('', 404)


@pytest.mark.parametrize(('config', 'appkey', 'expected'), [
    (book_config, '', "no 'CALIL_APPKEY' in environment variables"),
    ('', calil_appkey, "no 'BOOK_CONFIG' in environment variables"),
    (f'{testdir}/book-test-xxx.conf', calil_appkey,
     "cannot open configuration file "),
    (f'{testdir}/book-test-config-error.conf', calil_appkey,
     "cannot parse configuration"),
    (f'{testdir}/book-test-no-book.conf',
     calil_appkey,
     "'book' key not found in"),
])
def test_book_init_raise_no_key(config, appkey, expected):
    os.environ['BOOK_CONFIG'] = config
    os.environ['CALIL_APPKEY'] = appkey
    with pytest.raises(book.BookStatusError) as e:
        book.BookStatus()
    assert str(e.value).startswith(expected)


@pytest.mark.parametrize(('bk', 'expected0', 'expected1'), [
    ('Twitter', {'book': 'Twitter', 'data': {}}, r':.+:'),  # not found
    (
        'イマココ',
        {
            'book': 'イマココ',
            'data': {
                'イマココ 渡り鳥からグーグル・アースまで、空間認知の科学': {
                    'Tokyo_NDL': {
                        'name': '国立国会図書館',
                        'url': '',
                        'status': {}
                    },
                    'Tokyo_Pref': {
                        'name': '東京都立図書館',
                        'url': 'https://catalog.library.metro.tokyo.jp/winj/'
                               'opac/switch-detail-iccap.do?bibid=1108071029',
                        'status': {
                            '中央': '館内のみ'
                        }
                    }
                }
            }
        },
        '.イマココ.\n\nイマココ 渡り鳥からグーグル・アースまで、空間認知の科学\n'
        '(- 国立国会図書館: 蔵書なし\n- 東京都立図書館.中央.+\n|'
        '- 東京都立図書館.中央.+\n- 国立国会図書館: 蔵書なし\n)'
    )
])
def test_book_search(mocker, bk, expected0, expected1):
    mocker.patch('monibot.book.requests.get', side_effect=requests_mock)
    os.environ['BOOK_CONFIG'] = f'{testdir}/book-test.conf'
    os.environ['CALIL_APPKEY'] = calil_appkey

    bs = book.BookStatus()
    res = bs.search(bk)
    assert res[0] == expected0
    assert re.match(expected1, res[1])


if __name__ == '__main__':
    pytest.main(['-v', __file__])
