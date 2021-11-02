(ns feedreader.core-test
  (:require [clojure.test :refer :all]
            [clojure.java.io :as io]
            [feedreader.core :refer :all])
  (:import (org.sqlite SQLiteException)
           (java.time OffsetDateTime ZoneOffset)))

(def data "<rss version=\"2.0\"><channel><title>Website</title><link>https://localhost</link><description>Description</description><item><title>Item 1 title</title><link>https://localhost/item1</link><pubDate>Fri, 18 Jun 2021 20:38:40 +0000</pubDate><comments>https://localhost/item1/comments</comments></item><item><title>Item 2 title</title><link>https://localhost/item2</link><pubDate>Fri, 25 Jun 2021 20:38:40 +0000</pubDate><comments>https://localhost/item2/comments</comments></item></channel></rss>")

(deftest parse-feed-test
  (testing "parse-feed"
    ;https://www.rssboard.org/rss-specification
    (let [data-input-stream (io/input-stream (.getBytes data))
          parsed (parse-feed data-input-stream)]
      (is (= (first parsed) {:title  "Item 1 title", :link  "https://localhost/item1"}))
      (is (= (nth parsed 1) {:title  "Item 2 title", :link  "https://localhost/item2"})))))

(deftest test-filter-feed
  (testing "filter-feed"
    (let [data-input-stream (io/input-stream (.getBytes data))
          parsed (parse-feed data-input-stream)
          filtered (filter-items parsed #"item 1")]
      (is (= (count filtered) 1)))))

(deftest test-db-feed
  (testing "insert and read feed from db"
    (let [db-conn (get-db-conn ":memory:")
          feed {:name "Feed 1" :url "https://localhost/feed1"}
          feed-id 1]
      (create-tables db-conn)
      (insert-feed-into-db db-conn feed)
      (let [feeds (load-feeds db-conn)
            feed (first feeds)
            current-year (. (OffsetDateTime/now ZoneOffset/UTC) getYear)]
        (is (= (feed :url) "https://localhost/feed1"))
        (is (= (feed :name) "Feed 1"))
        (is (= (. (feed :created) getYear) current-year))
        (is (= (. (feed :last-modified) getYear) current-year))))))

(deftest test-db-entry
  (testing "insert and read entry from db"
    (let [db-conn (get-db-conn ":memory:")
          feed {:url "https://localhost/feed1"}
          feed-id 1
          entry {:title "title 1" :link "https://localhost/item1"}]
      (create-tables db-conn)
      (insert-feed-into-db db-conn feed)
      (insert-entry-into-db db-conn feed-id entry)
      (let [entries (load-entries-for-feed db-conn feed-id)]
        (is (= ((first entries) :link) "https://localhost/item1"))))))

(deftest test-db-entry-foreign-key
  (testing "foreign key to feeds table"
    (let [db-conn (get-db-conn ":memory:")
          entry {:title "title 1" :link "https://localhost/item1"}]
      (create-tables db-conn)
      (try
        (insert-entry-into-db db-conn 1 entry)
        (catch SQLiteException e))
      (let [entries (load-entries-for-feed db-conn 1)]
        (is (= (count entries) 0))))))

(deftest test-db-dup-entry
  (testing "insert duplicate entry"
    (let [db-conn (get-db-conn ":memory:")
          feed {:url "https://localhost/feed1"}
          feed-id 1
          entry {:title "title 1" :link "https://localhost/item1"}]
      (create-tables db-conn)
      (insert-feed-into-db db-conn feed)
      (insert-entry-into-db db-conn feed-id entry)
      (insert-entry-into-db db-conn feed-id entry)
      (let [entries (load-entries-for-feed db-conn feed-id)]
        (is (= (count entries) 1))))))
