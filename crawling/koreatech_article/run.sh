#!/bin/bash

mkdir -p logs

python3 /usr/local/KOIN_BATCH/crawling/koreatech_article/article.py 1 >> /usr/local/KOIN_BATCH/crawling/koreatech_article/logs/output1.log 2>&1 &
python3 /usr/local/KOIN_BATCH/crawling/koreatech_article/article.py 2 >> /usr/local/KOIN_BATCH/crawling/koreatech_article/logs/output2.log 2>&1 &
