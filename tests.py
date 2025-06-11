import os
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


if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)

        unittest.main()
