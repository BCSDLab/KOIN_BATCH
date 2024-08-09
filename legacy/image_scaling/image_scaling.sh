#!/bin/bash
source s3.config

aws s3 sync "$S3_PATH" "$LOCAL_PATH"

python3 "$PY_PATH"
echo "실행 완료"

aws s3 sync "$LOCAL_PATH" "$S3_PATH"
