#!/bin/bash

mkdir -p logs

python3 article.py 1 >> logs/output1.log 2>&1 &
python3 article.py 2 >> logs/output2.log 2>&1 &
