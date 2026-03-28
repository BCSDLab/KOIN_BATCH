#!/bin/bash

# 도움말 메시지 함수
usage() {
    echo "사용방법: $0 -n <file_name> -d <directory_path>"
    echo "  -n    (필수) 구동할 python 파일명을 지정합니다. ex) ./run.sh -n koreatech_dining"
    echo "  -d    프로젝트의 디렉터리를 지정합니다. 입력하지 않는다면 현재 작업 디렉토리를 기준으로 설정합니다."
    echo "  -h    도움말 메시지를 확인합니다."
    exit 1
}

# 현재 작업 디렉토리를 BASE_DIR로 설정
BASE_DIR="$(pwd)"

# run.sh 위치
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

while getopts "n:d:h" opt; do
    case $opt in
        n) FILE_NAME="$OPTARG" ;;
        d) BASE_DIR="$OPTARG" ;;
        h) usage ;;
        \?) usage ;;
    esac
done

# 인자가 하나도 없을 경우 도움말 출력
if [ $# -eq 0 ]; then
    usage
fi

# 파일 이름 인자 확인
if [ -z "$FILE_NAME" ]; then
    usage
fi

# 로그 디렉토리
LOG_DIR="$ROOT_DIR/logs"
FULL_LOG_DIR="$LOG_DIR/$FILE_NAME"
LOG_FILE="$FULL_LOG_DIR/$FILE_NAME.out"

# 로그 디렉토리 생성
mkdir -p "$FULL_LOG_DIR"

# 가상 환경 경로
VENV_DIR="$ROOT_DIR/myenv"

# 가상 환경 Python 실행 파일 경로
VENV_PYTHON="$VENV_DIR/bin/python"

# python3 실행 파일 경로 확인
PYTHON3_BIN="$(command -v python3)"

# python3 명령 확인
if [ -z "$PYTHON3_BIN" ]; then
    echo "python3 명령을 찾을 수 없습니다." >> "$LOG_FILE"
    exit 1
fi

# 가상 환경 확인 및 생성
if [ ! -x "$VENV_PYTHON" ]; then
    echo "Python 가상환경이 없습니다!" >> "$LOG_FILE"
    echo "가상환경을 생성합니다..." >> "$LOG_FILE"
    "$PYTHON3_BIN" -m venv "$VENV_DIR" >> "$LOG_FILE" 2>&1
fi

# 가상 환경 생성 결과 확인
if [ ! -x "$VENV_PYTHON" ]; then
    echo "가상환경 생성에 실패했습니다. $VENV_PYTHON 파일이 존재하지 않습니다." >> "$LOG_FILE"
    exit 1
fi

# requirements.txt 파일 존재 확인
if [ ! -f "$ROOT_DIR/requirements.txt" ]; then
    echo "requirements.txt 파일이 존재하지 않습니다: $ROOT_DIR/requirements.txt" >> "$LOG_FILE"
    exit 1
fi

# 실행할 python 파일 존재 확인
if [ ! -f "$BASE_DIR/$FILE_NAME.py" ]; then
    echo "실행할 python 파일이 존재하지 않습니다: $BASE_DIR/$FILE_NAME.py" >> "$LOG_FILE"
    exit 1
fi

# 필요한 패키지 설치
"$VENV_PYTHON" -m pip install -r "$ROOT_DIR/requirements.txt" >> "$LOG_FILE" 2>&1 || {
    echo "패키지 설치에 실패했습니다." >> "$LOG_FILE"
    exit 1
}

# 파이썬 스크립트 실행
"$VENV_PYTHON" "$BASE_DIR/$FILE_NAME.py" >> "$LOG_FILE" 2>&1 || {
    echo "파이썬 스크립트 실행에 실패했습니다." >> "$LOG_FILE"
    exit 1
}
