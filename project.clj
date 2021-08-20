(defproject feedreader "0.1.0-SNAPSHOT"
  :description "Feed Reader"
  :url "http://example.com/FIXME"
  :license {:name "MIT"}
  :dependencies [[org.clojure/clojure "1.10.3"]]
  :main ^:skip-aot feedreader.core
  :target-path "target/%s"
  :profiles {:uberjar {:aot :all}})
