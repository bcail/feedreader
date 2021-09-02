(ns feedreader.core
  (:require [clojure.xml :as xml]
            [clojure.java.io :as io])
  (:import (java.net.http HttpClient HttpRequest HttpResponse$BodyHandlers)
           (java.net URI)
           (java.sql DriverManager)
           (java.util.regex Pattern))
  (:gen-class))

(defn load-feeds
  [db-name]
  (let [connection (DriverManager/getConnection (str "jdbc:sqlite:" db-name))
        statement (.createStatement connection)
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

(defn -main
  "Feed Reader"
  [& args]
  (println "Welcome to Feed Reader")
  (let [db-name "feedreader.db"]
    (dorun
      (for [feed (load-feeds db-name)]
        (do
          (println (feed :url))
          (process-feed feed))))))
