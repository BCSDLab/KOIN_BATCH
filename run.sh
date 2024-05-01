#!/bin/bash

# 현재 작업 디렉토리를 BASE_DIR로 설정
BASE_DIR=$(pwd)

# 로그 디렉토리
LOG_DIR="$BASE_DIR/logs"

# 가상 환경 경로
VENV_DIR="$BASE_DIR/myenv"

# 인자 파싱
while getopts "n:" opt; do
  case $opt in
    n) FILE_NAME="$OPTARG"
    ;;
    \?) echo "Invalid option -$OPTARG" >&2
    exit 1
    ;;
  esac
done

# 파일 이름 인자 확인
if [ -z "$FILE_NAME" ]; then
  echo "잘못된 인자입니다!: $0 -n <file_name>"
  exit 1
fi

# 가상 환경 확인 및 생성
if [ ! -d "$VENV_DIR" ]; then
  echo "Python 가상환경이 없습니다!"
  echo "가상환경을 생성합니다..."
  python3 -m venv $VENV_DIR
fi

# 필요한 패키지 설치
pip3 install -r $BASE_DIR/requirements.txt

# 로그 디렉토리 생성
FULL_LOG_DIR="$LOG_DIR/$FILE_NAME"
mkdir -p $FULL_LOG_DIR

# 파이썬 스크립트 실행
python3 $BASE_DIR/crawling/koreatech_$FILE_NAME.py >> $FULL_LOG_DIR/$FILE_NAME.out 2>&1

