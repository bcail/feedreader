#!/usr/bin/env python3
from contextlib import contextmanager
import datetime
import re
import sqlite3
import sys
import urllib.request
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ParseError


DB_NAME = 'feedreader.db'

DB_INIT_STATEMENTS = [
    'CREATE TABLE feeds ('
        'id INTEGER PRIMARY KEY,'
        'url TEXT NOT NULL,'
        'name TEXT NOT NULL,'
        'filter TEXT NULL,'
        'inactive INTEGER NOT NULL DEFAULT 0,'
        'created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,'
        'updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,'
        'CHECK (inactive = 0 OR inactive = 1),'
        'UNIQUE(url)) STRICT',
    'CREATE TABLE entries ('
        'id INTEGER PRIMARY KEY,'
        'feedid INTEGER NOT NULL,'
        'url TEXT NOT NULL,'
        'external_id TEXT NOT NULL,'
        'title TEXT NOT NULL,'
        'date TEXT NULL,'
        'date_string TEXT NULL,'
        'description TEXT NOT NULL DEFAULT "",'
        'author TEXT NOT NULL DEFAULT "",'
        'enclosure_url TEXT NOT NULL DEFAULT "",'
        'created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,'
        'updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,'
        'UNIQUE(feedid, url, external_id, title),'
        'CHECK (date IS NULL OR date IS strftime("%Y-%m-%d %H:%M:%S", date)),'
        'FOREIGN KEY(feedid) REFERENCES feeds(id)) STRICT',
    'CREATE TRIGGER feed_updated UPDATE ON feeds BEGIN UPDATE feeds SET updated = CURRENT_TIMESTAMP WHERE id = old.id; END;',
    'CREATE TRIGGER entry_updated UPDATE ON entries BEGIN UPDATE entries SET updated = CURRENT_TIMESTAMP WHERE id = old.id; END;',
]


@contextmanager
def sqlite_txn(cursor):
    cursor.execute('BEGIN IMMEDIATE')
    try:
        yield
        cursor.execute('COMMIT')
    except BaseException as e:
        cursor.execute('ROLLBACK')
        raise


def _get_db_connection(db_name):
    conn = sqlite3.connect(db_name, isolation_level=None)
    conn.execute('PRAGMA foreign_keys = ON;')
    return conn


def create_tables(conn):
    cursor = conn.cursor()
    with sqlite_txn(cursor):
        for statement in DB_INIT_STATEMENTS:
            cursor.execute(statement)


def _get_feeds(conn):
    query = 'SELECT id,name,url,filter,inactive FROM feeds ORDER BY id'
    feed_records = conn.execute(query).fetchall()
    feeds = []
    for r in [f for f in feed_records if not f[4]]:
        info = {
            'id': r[0],
            'name': r[1],
            'url': r[2],
            'filter': r[3],
        }
        feeds.append(info)
    return feeds


def _get_date(d):
    for format_ in ['%a, %d %b %Y %H:%M:%S %z', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%d %H:%M:%S%z', '%Y-%m-%dT%H:%M:%S.%f%z',
                    '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%SZ', '%Y-%m-%d %H:%M:%S', '%a, %d %b %Y %H:%M:%S GMT']:
        try:
            return datetime.datetime.strptime(d, format_)
        except ValueError:
            pass


def _parse_feed(data, feed_info):
    items = []
    try:
        tree = ET.fromstring(data)
    except ParseError as e:
        print(f'{feed_info} -- error parsing feed: {e}')
        return []
    #rss - https://www.rssboard.org/rss-specification
    if tree.tag == 'rss':
        # tree[0] is <channel>
        for child in tree[0]:
            if child.tag == 'item':
                info = {}
                for item_child in child:
                    if item_child.tag == 'title':
                        info['title'] = item_child.text
                    elif item_child.tag == 'link':
                        info['url'] = item_child.text
                    elif item_child.tag == 'guid':
                        info['external_id'] = item_child.text
                    elif item_child.tag == 'enclosure':
                        info['enclosure_url'] = item_child.attrib['url']
                    elif item_child.tag == 'pubDate':
                        pub_date = _get_date(item_child.text)
                        if pub_date:
                            info['date'] = pub_date
                        else:
                            info['date_string'] = item_child.text
                items.append(info)
    #atom - https://validator.w3.org/feed/docs/atom.html
    elif tree.tag == '{http://www.w3.org/2005/Atom}feed':
        for child in tree:
            if child.tag == '{http://www.w3.org/2005/Atom}entry':
                info = {}
                for entry_child in child:
                    if entry_child.tag == '{http://www.w3.org/2005/Atom}title':
                        info['title'] = entry_child.text
                    if entry_child.tag == '{http://www.w3.org/2005/Atom}link':
                        rel = entry_child.attrib.get('rel', 'alternate')
                        if rel == 'alternate':
                            info['url'] = entry_child.attrib['href']
                        elif rel == 'enclosure':
                            info['enclosure_url'] = entry_child.attrib['href']
                    if entry_child.tag == '{http://www.w3.org/2005/Atom}id':
                        info['external_id'] = entry_child.text
                    if entry_child.tag == '{http://www.w3.org/2005/Atom}updated':
                        # eg. 2024-05-29T00:00:00-04:00
                        updated = _get_date(entry_child.text)
                        if updated:
                            info['date'] = updated
                        else:
                            info['date_string'] = entry_child.text
                items.append(info)
    else:
        print(f'{feed_info} -- can\'t parse {tree.tag}')
    return items


def _filter_items(items, pattern):
    if not pattern:
        return items[:]
    filtered = []
    for i in items:
        title = i['title'].lower()
        if re.search(pattern, title):
            filtered.append(i)
    return filtered


def _insert_feed(conn, feed):
    values = [feed['name'], feed['url'], feed['filter']]
    if feed['inactive']:
        values.append(1)
    else:
        values.append(0)
    cur = conn.cursor()
    with sqlite_txn(cur):
        cur.execute('INSERT INTO feeds(name, url, filter, inactive) VALUES(?, ?, ?, ?)', values)
        id_ = cur.lastrowid
        return id_


def _insert_item(conn, item, feedid):
    #db is unique across feedid, title, link, & external_id - need to use '' for those, instead of null,
    #   so unique works
    dt = item.get('date')
    if dt:
        dt = dt.strftime('%Y-%m-%d %H:%M:%S')
    values = (feedid, item['title'] or '', item.get('url') or '', item.get('external_id') or '', item.get('enclosure_url', ''),
              dt, item.get('date_string'))
    cur = conn.cursor()
    try:
        with sqlite_txn(cur):
            cur.execute('INSERT INTO entries(feedid, title, url, external_id, enclosure_url, date, date_string) VALUES(?, ?, ?, ?, ?, ?, ?)', values)
            id_ = cur.lastrowid
            return id_
    except Exception as e:
        if 'UNIQUE constraint failed' in str(e):
            return
        raise


request_headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux i686; rv:125.0) Gecko/20100101 Firefox/125.0'
}


def _fetch_feed(url, feed_info=None):
    if not feed_info:
        feed_info = url
    req = urllib.request.Request(url, headers=request_headers.copy())
    try:
        response = urllib.request.urlopen(req)
        if response.status == 200:
            data = response.read()
            return data
        else:
            print(f'{feed_info} error: {response.status}')
    except Exception as e:
        print(f'{feed_info} error: {e}')


def _url_is_image(url):
    url = url.lower()
    if url.endswith('jpg') or url.endswith('png'):
        return True


def fetch_feeds(db_name=DB_NAME):
    conn = _get_db_connection(db_name)
    feeds = _get_feeds(conn)
    for feed in feeds:
        feed_info = f'{feed["name"]} -- {feed["url"]}'
        data = _fetch_feed(feed['url'], feed_info)
        if data:
            items = _parse_feed(data, feed_info)
            filtered_items = _filter_items(items, feed['filter'])
            if filtered_items:
                items_to_print = []
                for item in filtered_items:
                    id_ = _insert_item(conn, item, feed['id'])
                    if id_:
                        description = ''
                        if 'url' in item:
                            description = item["url"]
                        elif 'id' in item:
                            description = item["id"]
                        if 'enclosure_url' in item:
                            if not _url_is_image(item['enclosure_url']):
                                description += f' ({item["enclosure_url"]})'
                        items_to_print.append(f'{id_} - {item["title"]}\n  {description}')
                if items_to_print:
                    print(f'\n***** {feed_info}')
                    print('\n'.join(items_to_print))


def _list_feeds(db_name=DB_NAME):
    conn = _get_db_connection(db_name)
    feeds = _get_feeds(conn)
    for f in feeds:
        feed_info = f'{f["id"]} -- {f["name"]} -- {f["url"]}'
        print(feed_info)


def _list_entries(db_name=DB_NAME):
    conn = _get_db_connection(db_name)
    feeds = _get_feeds(conn)
    for f in feeds:
        print(f'\n*** {f["name"]} ***\n')
        entries = conn.execute('SELECT date,title,url,enclosure_url,date_string FROM entries WHERE feedid = ? ORDER BY date DESC LIMIT 5', (f['id'],)).fetchall()
        for e in entries:
            if e[0]:
                d = e[0].split()[0]
                info = f'{d} -- {e[1]}'
            else:
                info = e[1]
            if e[2]:
                info += f'\n  -- {e[2]}'
            if e[3] and not _url_is_image(e[3]):
                info += f'  -- {e[3]}'
            elif e[4]:
                info += f'  -- {e[4]}'
            print(info)


cmds = {
    'f': {'description': 'list feeds', 'function': _list_feeds},
    'e': {'description': 'list entries', 'function': _list_entries},
}


def _print_help(cmds):
    help_msg = 'h - help'
    for cmd, info in cmds.items():
        help_msg += f'\n{cmd} - {info["description"]}'
    help_msg += '\nq (or Ctrl-d) - quit'
    print(help_msg.strip())


def _command_loop(cmds):
    while True:
        cmd = input('>>> ')
        if cmd == 'h':
            _print_help(cmds)
        elif cmd == 'q':
            raise EOFError()
        elif cmd in cmds:
            cmds[cmd]['function']()
        else:
            print('Invalid command: "%s"' % cmd)


def run():
    _print_help(cmds)
    try:
        _command_loop(cmds)
    except (EOFError, KeyboardInterrupt):
        sys.exit(0)
    except:
        import traceback
        print(traceback.format_exc())
        sys.exit(1)


def parse_args():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--fetch', action='store_true', dest='fetch')
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    print('Welcome to Feed Reader')

    args = parse_args()

    if args.fetch:
        fetch_feeds()
    else:
        run()
