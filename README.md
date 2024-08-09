# KOIN BATCH 프로젝트

BATCH로 구동되는 작업을 모아둔 프로젝트입니다.

# 환경구성

프로젝트에 포함되어있는 run.sh 파일을 활용하여 프로젝트를 구동할 수 있습니다.

**사용 전 실행권한을 부여해주세요.**

```shell
chmod +x run.sh
chmod +x venv.sh
```

> 사용예시

```shell
run.sh -n koreatech_notice -d /usr/local/KOIN_BATCH 
```

```shell
run.sh -h
```

## Crontab

Crontab을 활용하여 스케줄링을 구성할 수도 있습니다.

> 사용 예시

```shell
# notice batch
0 5 * * * bash ~/KOIN_BATCH/run.sh -n koreatech_notice > /dev/null 2>&1
```

# env
[Poetry](https://python-poetry.org/)를 사용하여 가상 환경을 관리합니다.
프로젝트에 포함되어있는 venv.sh 파일을 활용하여 프로젝트를 구동할 수 있습니다.

*venv.sh에서 poetry가 설치되어 있지 않은 경우 설치합니다.  
따라서 직접 설치할 필요는 없습니다.*
```bash
# 선택 사항
pip install poetry
```

**사용 전 실행권한을 부여해주세요.**

```bash
chmod +x venv.sh
```

> 사용 예시

```bash
./venv.sh
```

# TODO
- [ ] run.sh 수정 필요
