#!/usr/bin/env python3

import os
import re
import pytest
import monibot.book as book

os.environ['BOOK_CONFIG'] = 'book_config_dummy'
os.environ['CALIL_APPKEY'] = 'calil_appkey_dummy'
book_config = os.environ['BOOK_CONFIG']
calil_appkey = os.environ['CALIL_APPKEY']
testdir = 'tests/monibot'


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
    ('Twiter', {'book': 'Twiter', 'data': {}}, r':.+:'),  # not found
    (
        '血と汗とピクセル',
        {
            'book': '血と汗とピクセル',
            'data': {
                '血と汗とピクセル : 大ヒットゲーム開発者たちの激戦記': {
                    'Tokyo_Pref': {
                        'name': '東京都立図書館',
                        'url': '',
                        'status': {}
                    },
                    'Tokyo_NDL': {
                        'name': '国立国会図書館',
                        'url': 'https://ndlsearch.ndl.go.jp/books/R100000002-I029742144',
                        'status': {'東京本館': '蔵書あり'}
                    }
                }
            }
        },
        '[血と汗とピクセル]\n\n血と汗とピクセル : 大ヒットゲーム開発者たちの激戦記\n'
        '- 東京都立図書館: 蔵書なし\n'
        '- 国立国会図書館(東京本館): <https://ndlsearch.ndl.go.jp/books/R100000002-I029742144|蔵書あり>\n'
    ),
])
def test_book_search(mocker, bk, expected0, expected1):
    os.environ['BOOK_CONFIG'] = f'{testdir}/book-test.conf'
    os.environ['CALIL_APPKEY'] = calil_appkey

    bs = book.BookStatus()
    res = bs.search(bk)
    assert res[0] == expected0
    if bk == 'Twiter':
        assert re.match(expected1, res[1])
    else:
        r = res[1].split('\n')
        for e in expected1.split('\n'):
            assert e in r


def test_normalize_isbn():
    patterns = [
        ("978-4-8222-8993-5", "9784822289935"),
        ("978-4834084375", "9784834084375"),
        ("9784834084375", "9784834084375"),
        ("483408437X", "483408437X"),
        ("4822245640", "4822245640"),
        ("978-4822245641", "9784822245641"),
        ("978-482224564", ""),
        ("483408437x", ""),
        ("483408437", ""),
    ]
    bs = book.BookStatus()
    for pattern, expected in patterns:
        result = bs.normalize_isbn(pattern)
        assert result == expected


if __name__ == '__main__':
    pytest.main(['-v', __file__])
