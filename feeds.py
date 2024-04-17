import re
import sqlite3
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


def _parse_feed(data):
    items = []
    try:
        tree = ET.fromstring(data)
    except ParseError as e:
        print(f'  error parsing feed: {e}')
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
        print(f'  can\'t parse {tree.tag}')
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


def _fetch_feed(url):
    req = urllib.request.Request(url, headers=request_headers.copy())
    try:
        response = urllib.request.urlopen(req)
        if response.status == 200:
            data = response.read()
            return data
        else:
            print(f'  error: {response.status}')
    except Exception as e:
        print(f'  {e}')


def run(db_name=DB_NAME):
    conn = _get_db_connection(db_name)
    feeds = _get_feeds(conn)
    for feed in feeds:
        print(f'\n***** {feed["name"]} -- {feed["url"]}')
        data = _fetch_feed(feed['url'])
        if data:
            items = _parse_feed(data)
            filtered_items = _filter_items(items, feed['filter'])
            for item in filtered_items:
                id_ = _insert_item(conn, item, feed['id'])
                if id_:
                    description = ''
                    if 'link' in item:
                        description = item["link"]
                    elif 'id' in item:
                        description = item["id"]
                    print(f'{id_} - {item["title"]}\n  ({description})')


if __name__ == '__main__':
    print('Welcome to Feed Reader')
    run()
