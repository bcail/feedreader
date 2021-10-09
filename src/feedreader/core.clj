(ns feedreader.core
  (:require [clojure.xml :as xml]
            [clojure.java.io :as io])
  (:import (java.net.http HttpClient HttpRequest HttpResponse$BodyHandlers)
           (java.net URI)
           (java.sql DriverManager)
           (java.util.regex Pattern)
           (org.sqlite SQLiteException))
  (:gen-class))

(defn get-db-conn
  [db-name]
  (DriverManager/getConnection (str "jdbc:sqlite:" db-name)))

(defn create-tables
  [db-conn]
  (let [statement (.createStatement db-conn)]
    (.executeUpdate statement "CREATE TABLE feeds (id INTEGER PRIMARY KEY, url TEXT, filter TEXT)")
    (.executeUpdate statement "CREATE TABLE entries (id INTEGER PRIMARY KEY, feedid INTEGER, title TEXT, link TEXT, UNIQUE(feedid, title, link))")))

(defn insert-feed-into-db
  [db-conn feed]
  (let [statement (.createStatement db-conn)]
    (.executeUpdate statement (str "INSERT INTO feeds (url, filter) VALUES (\"" (feed :url) "\", \"" (get feed :filter "") "\")"))))

(defn insert-entry-into-db
  [db-conn feed-id entry]
  (let [statement (.createStatement db-conn)
        title (get entry :title "")
        link (entry :link)
        insert-stmt (str "INSERT INTO entries (feedid, title, link) VALUES (" feed-id ", \"" title "\", \"" link "\")")]
    ;org.sqlite.SQLiteException:  [SQLITE_CONSTRAINT_UNIQUE]  A UNIQUE constraint failed]
    (try
      (.executeUpdate statement insert-stmt)
      (catch SQLiteException e))))

(defn load-feeds
  [db-conn]
  (let [statement (.createStatement db-conn) ;should be PreparedStatement
        results (.executeQuery statement "SELECT * FROM feeds")]
    (loop [feeds []]
      (if (not (.next results))
        feeds
        (recur (conj feeds
                    {:id (.getInt results "id")
                     :url (.getString results "url")
                     :filter (Pattern/compile (.getString results "filter"))}))))))

(defn load-entries-for-feed
  [db-conn feed-id]
  (let [statement (.createStatement db-conn)
        results (.executeQuery statement (str "SELECT * FROM entries WHERE feedid = " feed-id))]
    (loop [entries []]
      (if (not (.next results))
        entries
        (recur (conj entries
                     {:title (.getString results "title")
                      :link (.getString results "link")}))))))

(defn fetch-url
  [url]
  (let [client (HttpClient/newHttpClient)
        request (.build (.uri (HttpRequest/newBuilder) (URI/create url)))
        body (HttpResponse$BodyHandlers/ofString)
        response (.send client request body)]
    (.body response))
  )

(defn parse-feed
  [data]
  (let [input-stream (io/input-stream (.getBytes data))]
    (for [x (:content ((:content (xml/parse input-stream)) 0)) :when (= :item (:tag x))]
      {
        :title ((:content ((:content x) 0)) 0)
        :link ((:content ((:content x) 1)) 0)
      }
    )))

(defn filter-items
  [items pattern]
  (for [i items :when (re-seq pattern (.toLowerCase (i :title)))]
    i))

(defn process-feed
  [db-conn feed]
  (dorun
    (for [entry (filter-items (parse-feed (fetch-url (feed :url))) (feed :filter))]
      (do
       (insert-entry-into-db db-conn (feed :id) entry)
       (println (str (entry :title) "\n  (" (entry :link) ")"))))))

(defn run
  [db-conn]
  (dorun
    (for [feed (load-feeds db-conn)]
      (do
        (println (feed :url))
        (process-feed db-conn feed)))))

(defn -main
  "Feed Reader"
  [& args]
  (println "Welcome to Feed Reader")
  (let [db-name "feedreader.db"]
    (run (get-db-conn db-name))))
