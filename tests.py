import os
import sqlite3
import tempfile
import unittest

import feeds


class Tests(unittest.TestCase):

    def setUp(self):
        self.conn = feeds._get_db_connection(':memory:')

        feeds.create_tables(self.conn)

    def test_insert_feed(self):
        feed_id = feeds.insert_feed({'name': 'Test Feed', 'url': 'http://localhost'}, conn=self.conn)

        cur = self.conn.cursor()

        results = cur.execute('SELECT id, name FROM feeds').fetchall()

        self.assertEqual(results, [(1, 'Test Feed')])

    def test_insert_entry_no_feedid(self):
        with self.assertRaises(sqlite3.IntegrityError) as cm:
            feeds.insert_item(self.conn, {}, None)

        self.assertIn('NOT NULL constraint failed: entries.feedid', str(cm.exception))

    def test_insert_entry(self):
        feed_id = feeds.insert_feed({'name': 'Test Feed', 'url': 'http://localhost'}, conn=self.conn)

        entry_id = feeds.insert_item(self.conn, {'title': 'Test Title', 'url': 'http://localhost'}, feed_id)

        cur = self.conn.cursor()

        results = cur.execute('SELECT id, title, url FROM entries').fetchall()

        self.assertEqual(results, [(1, 'Test Title', 'http://localhost')])


if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)

        unittest.main()
