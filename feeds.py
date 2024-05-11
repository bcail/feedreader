import re
import sqlite3
import sys
import urllib.request
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ParseError


DB_NAME = 'feedreader.db'


def _get_db_connection(db_name):
    return sqlite3.connect(db_name)


def _get_feeds(conn):
    query = 'SELECT id,name,url,filter,inactive FROM feeds'
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


def _parse_feed(data, feed_info):
    items = []
    try:
        tree = ET.fromstring(data)
    except ParseError as e:
        print(f'{feed_info} -- error parsing feed: {e}')
        return []
    if tree.tag == 'rss':
        # tree[0] is <channel>
        for child in tree[0]:
            if child.tag == 'item':
                info = {}
                for item_child in child:
                    if item_child.tag in ['title', 'link']:
                        info[item_child.tag] = item_child.text
                items.append(info)
    #atom
    elif tree.tag == '{http://www.w3.org/2005/Atom}feed':
        for child in tree:
            if child.tag == '{http://www.w3.org/2005/Atom}entry':
                info = {}
                for entry_child in child:
                    if entry_child.tag == '{http://www.w3.org/2005/Atom}title':
                        info['title'] = entry_child.text
                    if entry_child.tag == '{http://www.w3.org/2005/Atom}id':
                        info['id'] = entry_child.text
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


def _insert_item(conn, item, feedid):
    #db is unique across feedid, title, link, & guid - need to use '' for those, instead of null,
    #   so unique works
    values = (feedid, item['title'], None, item.get('link', ''), item.get('id', ''))
    try:
        cur = conn.cursor()
        cur.execute('INSERT INTO entries(feedid, title, description, link, guid) VALUES(?, ?, ?, ?, ?)', values)
        id_ = cur.lastrowid
        conn.commit()
        return id_
    except sqlite3.IntegrityError as e:
        if 'UNIQUE constraint failed' in str(e):
            return
        raise


request_headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux i686; rv:125.0) Gecko/20100101 Firefox/125.0'
}


def _fetch_feed(url, feed_info):
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
                        if 'link' in item:
                            description = item["link"]
                        elif 'id' in item:
                            description = item["id"]
                        items_to_print.append(f'{id_} - {item["title"]}\n  ({description})')
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
    print('Recent entries:')
    entries = conn.execute('SELECT title,link FROM entries ORDER BY created DESC LIMIT 20').fetchall()
    for e in entries:
        print(f'{e[0]} -- {e[1]}')


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
