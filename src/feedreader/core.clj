(ns feedreader.core
  (:require [clojure.xml :as xml]
            [clojure.string :as string])
  (:import (java.net.http HttpClient HttpRequest HttpResponse$BodyHandlers)
           (java.net URI)
           (java.sql DriverManager)
           (java.util.regex Pattern)
           (java.time OffsetDateTime)
           (java.time.format DateTimeFormatter)
           (org.sqlite SQLiteException SQLiteConfig))
  (:gen-class))

(defn get-db-conn
  [db-name]
  (let [config (doto (new SQLiteConfig) (.enforceForeignKeys true))]
    (DriverManager/getConnection (str "jdbc:sqlite:" db-name) (.toProperties config))))

(defn create-tables
  [db-conn]
  (let [statement (.createStatement db-conn)]
    (.executeUpdate statement "CREATE TABLE feeds (id INTEGER PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL, filter TEXT NULL, created TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')), UNIQUE(url))")
    (.executeUpdate statement "CREATE TABLE entries (id INTEGER PRIMARY KEY, feedid INTEGER NOT NULL, title TEXT NULL, description TEXT NULL, author TEXT NULL, guid TEXT NULL, link TEXT NULL, created TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')), UNIQUE(feedid, title, link, guid), FOREIGN KEY(feedid) REFERENCES feeds(id))")))

(defn insert-feed-into-db
  [db-conn feed]
  (let [statement (.createStatement db-conn)]
    (.executeUpdate statement (str "INSERT INTO feeds (name, url, filter) VALUES (\"" (feed :name) "\", \"" (feed :url) "\", \"" (get feed :filter "") "\")"))))

(defn insert-entry-into-db
  [db-conn feed-id entry]
  (let [statement (.createStatement db-conn)
        title (get entry :title "")
        description (get entry :description "")
        link (entry :link)
        guid (get entry :guid "")
        insert-stmt (str "INSERT INTO entries (feedid, title, description, link, guid) VALUES (" feed-id ", \"" title "\", \"" description "\", \"" link "\", \"" guid "\")")]
    ;these entries might already be in the DB, so just ignore unique exceptions
    ;org.sqlite.SQLiteException:  [SQLITE_CONSTRAINT_UNIQUE]  A UNIQUE constraint failed]
    (try
      (.executeUpdate statement insert-stmt)
      (catch SQLiteException e
        (let [exc-msg (.getMessage e)]
          (if (not (string/starts-with? exc-msg "[SQLITE_CONSTRAINT_UNIQUE]"))
            (throw e)))))))

(defn load-feeds
  [db-conn]
  (let [statement (.createStatement db-conn) ;should be PreparedStatement
        results (.executeQuery statement "SELECT * FROM feeds")]
    (loop [feeds []]
      (if (not (.next results))
        feeds
        (recur (conj feeds
                    {:id (.getInt results "id")
                     :name (.getString results "name")
                     :url (.getString results "url")
                     :filter (Pattern/compile (.getString results "filter"))
                     :created (OffsetDateTime/parse (.getString results "created") DateTimeFormatter/ISO_DATE_TIME)}))))))

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
        body (HttpResponse$BodyHandlers/ofInputStream)
        response (.send client request body)]
    (.body response))
  )

(defn parse-feed
  [data-input-stream]
  (for [x (:content ((:content (xml/parse data-input-stream)) 0)) :when (= :item (:tag x))]
    {
      :title ((:content ((:content x) 0)) 0)
      :link ((:content ((:content x) 1)) 0)
    }
  ))

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
