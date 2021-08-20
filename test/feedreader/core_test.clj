(ns feedreader.core-test
  (:require [clojure.test :refer :all]
            [feedreader.core :refer :all]))

(deftest parse-feed-test
  (testing "parse-feed"
    ;https://www.rssboard.org/rss-specification
    (let [data "<rss version=\"2.0\"><channel><title>Website</title><link>https://localhost</link><description>Description</description><item><title>Item 1 title</title><link>https://localhost/item1</link><pubDate>Fri, 18 Jun 2021 20:38:40 +0000</pubDate><comments>https://localhost/item1/comments</comments></item><item><title>Item 2 title</title><link>https://localhost/item2</link><pubDate>Fri, 25 Jun 2021 20:38:40 +0000</pubDate><comments>https://localhost/item2/comments</comments></item></channel></rss>"
          parsed (parse-feed data)]
      (is (= (first parsed) {:title  "Item 1 title", :link  "https://localhost/item1"}))
      (is (= (nth parsed 1) {:title  "Item 2 title", :link  "https://localhost/item2"})))))
