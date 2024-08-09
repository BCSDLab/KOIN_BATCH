#!/bin/bash

# 도움말 메시지 함수
usage() {
  echo "사용방법: $0 <option> <spider name>"
  echo "  -l    사용 가능한 크롤러 목록을 확인합니다."
  echo "  -h    도움말 메시지를 확인합니다."
  echo "(필수) 구동할 spider 이름을 지정합니다. ex) ./run.sh dining"
  exit 1
}

# spider 목록 보여주기 함수
list_spiders() {
  venv
  echo "실행 가능한 spider 목록:"
  poetry run scrapy list
  exit 0
}

# 가상 환경 확인 및 생성 (의존성 설치 포함)
venv() {
  local message="$1"
  if [ -f "$BASE_DIR/venv.sh" ]; then
    if [ -n "$message" ]; then
      echo "$message"
    fi
    bash "$BASE_DIR/venv.sh" >> "$BASE_DIR/venv.log" 2>&1
  else
    echo "Error: venv.sh 파일을 찾을 수 없습니다."
    exit 1
  fi
}

# 현재 작업 디렉토리를 프로젝트 디렉토리로 설정 (스크립트가 있는 디렉토리를 기준으로 설정)
BASE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

while getopts "lh" opt; do
  case $opt in
    l) list_spiders
    ;;
    h) usage
    ;;
    \?) usage
    ;;
  esac
done

# optind를 이용하여 non-option 인자의 시작 위치로 이동
shift $((OPTIND-1))

# 인자가 하나도 없거나, 1보다 큰 경우 도움말 출력
if [ $# -eq 0 ] || [ $# -gt 1 ]; then
    usage
fi

SPIDER_NAME="$1"

# 파일 이름 인자 확인
if [ -z "$SPIDER_NAME" ]; then
  usage
fi

venv "가상 환경 설정 중..."
poetry run scrapy crawl "$SPIDER_NAME"
