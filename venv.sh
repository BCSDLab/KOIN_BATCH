#!/bin/bash

# 프로젝트 경로 설정 (스크립트가 있는 디렉토리를 기준으로 설정)
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# 프로젝트 디렉토리로 이동
cd "$PROJECT_DIR" || exit

echo "프로젝트 디렉토리: $PROJECT_DIR"

# Poetry가 설치되어 있는지 확인
if ! command -v poetry &> /dev/null
then
    echo "Poetry가 설치되어 있지 않습니다. pip을 사용하여 설치를 시작합니다..."
    pip install poetry
fi

# Poetry 설정: 가상 환경을 프로젝트 디렉토리 내에 생성
poetry config virtualenvs.in-project true

# pyproject.toml 파일 존재 확인
if [ ! -f "pyproject.toml" ]; then
    echo "Error: pyproject.toml 파일을 찾을 수 없습니다. 올바른 디렉토리에서 스크립트를 실행하고 있는지 확인해주세요."
    exit 1
fi

# pyproject.toml에서 Python 버전 추출 (정확한 버전만)
PYTHON_VERSION=$(grep "^python = " pyproject.toml | sed -E 's/python = "\^?([0-9]+(\.[0-9]+){0,2}).*/\1/')

if [ -z "$PYTHON_VERSION" ]
then
    echo "pyproject.toml에서 Python 버전을 찾을 수 없습니다."
    exit 1
fi

echo "Python 버전 $PYTHON_VERSION 사용"

# 해당 버전의 Python으로 가상 환경 생성
poetry env use "$PYTHON_VERSION"

# 의존성 설치 (루트 프로젝트 제외)
poetry install --no-root

echo "환경 설정 완료"
