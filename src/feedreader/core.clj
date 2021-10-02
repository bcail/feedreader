(ns feedreader.core
  (:require [clojure.xml :as xml]
            [clojure.java.io :as io])
  (:import (java.net.http HttpClient HttpRequest HttpResponse$BodyHandlers)
           (java.net URI)
           (java.sql DriverManager)
           (java.util.regex Pattern))
  (:gen-class))

(defn get-db-conn
  [db-name]
  (DriverManager/getConnection (str "jdbc:sqlite:" db-name)))

(defn create-tables
  [db-conn]
  (let [statement (.createStatement db-conn)]
    (.executeUpdate statement "CREATE TABLE feeds (id INTEGER PRIMARY KEY, url TEXT, filter TEXT)")))

(defn insert-feed-into-db
  [db-conn feed]
  (let [statement (.createStatement db-conn)]
    (.executeUpdate statement (str "INSERT INTO feeds (url, filter) VALUES (\"" (feed :url) "\", \"" (get feed :filter "") "\")"))))

(defn load-feeds
  [db-conn]
  (let [statement (.createStatement db-conn) ;should be PreparedStatement
        results (.executeQuery statement "SELECT * FROM feeds")]
    (loop [feeds []]
      (if (not (.next results))
        feeds
        (recur (conj feeds
                    {:url (.getString results "url")
                     :filter (Pattern/compile (.getString results "filter"))}))))))

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
  [feed]
  (dorun
    (for [i (filter-items (parse-feed (fetch-url (feed :url))) (feed :filter))]
      (println (str (i :title) "\n  (" (i :link) ")")))))

(defn run
  [db-conn]
  (dorun
    (for [feed (load-feeds db-conn)]
      (do
        (println (feed :url))
        (process-feed feed)))))

(defn -main
  "Feed Reader"
  [& args]
  (println "Welcome to Feed Reader")
  (let [db-name "feedreader.db"]
    (run (get-db-conn db-name))))
