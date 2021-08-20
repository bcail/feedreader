(ns feedreader.core
  (:require [clojure.xml :as xml]
            [clojure.java.io :as io])
  (:import (java.net.http HttpClient HttpRequest HttpResponse$BodyHandlers)
           (java.net URI))
  (:gen-class))

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

(defn -main
  "Feed Reader"
  [& args]
  (println "Welcome to Feed Reader"))
