import re
import sqlite3
import urllib.request
import xml.etree.ElementTree as ET


DB_NAME = 'feedreader.db'


def _get_feeds(conn):
    query = 'SELECT id,name,url,filter FROM feeds'
    feed_records = conn.execute(query).fetchall()
    feeds = []
    for r in feed_records:
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
    tree = ET.fromstring(data)
    # tree[0] is <channel>
    for child in tree[0]:
        if child.tag == 'item':
            info = {}
            for item_child in child:
                if item_child.tag in ['title', 'link']:
                    info[item_child.tag] = item_child.text
            items.append(info)
    return items


def _filter_items(items, pattern):
    filtered = []
    for i in items:
        title = i['title'].lower()
        if re.search(pattern, title):
            filtered.append(i)
    return filtered


def _insert_item(conn, item, feedid):
    values = (feedid, item['title'], '', item['link'], '')
    try:
        conn.execute('INSERT INTO entries(feedid, title, description, link, guid) VALUES(?, ?, ?, ?, ?)', values)
        conn.commit()
        return True
    except sqlite3.IntegrityError as e:
        if 'UNIQUE constraint failed' in str(e):
            return
        raise


def run(db_name=DB_NAME):
    conn = sqlite3.connect(db_name)
    feeds = _get_feeds(conn)
    for feed in feeds:
        print(f'\n***** {feed["name"]} -- {feed["url"]}')
        response = urllib.request.urlopen(feed['url'])
        if response.status == 200:
            data = response.read()
            items = _parse_feed(data)
            filtered_items = _filter_items(items, feed['filter'])
            for item in filtered_items:
                result = _insert_item(conn, item, feed['id'])
                if result:
                    print(f'{item["title"]}\n  ({item["link"]})')
        else:
            print(f'  error: {response.status}')


if __name__ == '__main__':
    print('Welcome to Feed Reader')
    run()
