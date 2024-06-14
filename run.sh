#!/bin/bash

# 현재 작업 디렉토리를 BASE_DIR로 설정
BASE_DIR=$(pwd)

# 로그 디렉토리
LOG_DIR="$BASE_DIR/logs"

# 가상 환경 경로
VENV_DIR="$BASE_DIR/myenv"

# 도움말 메시지 함수
usage() {
    echo "사용방법: $0 -n <file_name> -d <directory_path>"
    echo "  -n    (필수) 구동할 python 파일명을 지정합니다. ex) ./run.sh -n koreatech_dining"
    echo "  -d    프로젝트의 디렉터리를 지정합니다. 입력하지 않는다면 현재 작업 디렉토리를 기준으로 설정합니다."
    echo "  -h    도움말 메시지를 확인합니다."
    exit 1
}

# 인자가 하나도 없을 경우 도움말 출력
if [ $# -eq 0 ]; then
    usage
fi

while getopts "n:d:h" opt; do
  case $opt in
    n) FILE_NAME="$OPTARG"
    ;;
    d) BASE_DIR="$OPTARG"
    ;;
    h) usage
    ;;
    \?) usage
    ;;
  esac
done

# 파일 이름 인자 확인
if [ -z "$FILE_NAME" ]; then
  useage
fi

# 가상 환경 확인 및 생성
if [ ! -d "$VENV_DIR" ]; then
  echo "Python 가상환경이 없습니다!"
  echo "가상환경을 생성합니다..."
  python3 -m venv $VENV_DIR >> $FULL_LOG_DIR/$FILE_NAME.out 2>&1
fi

# 로그 디렉토리 생성
FULL_LOG_DIR="$LOG_DIR/$FILE_NAME"
mkdir -p $FULL_LOG_DIR

# 필요한 패키지 설치
pip3 install -r $BASE_DIR/requirements.txt >> $FULL_LOG_DIR/$FILE_NAME.out 2>&1

# 파이썬 스크립트 실행
python3 $BASE_DIR/$FILE_NAME.py >> $FULL_LOG_DIR/$FILE_NAME.out 2>&1