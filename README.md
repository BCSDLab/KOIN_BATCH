# KOIN BATCH 프로젝트

BATCH로 구동되는 작업을 모아둔 프로젝트입니다.

# 환경구성

프로젝트에 포함되어있는 run.sh 파일을 활용하여 프로젝트를 구동할 수 있습니다.

> 사용예시

```shell
run.sh -n koreatech_notice 
```

## Crontab

Crontab을 활용하여 스케줄링을 구성할 수도 있습니다.

> 사용 예시

```shell
# notice batch
0 5 * * * bash ~/KOIN_BATCH/run.sh -n koreatech_notice > /dev/null 2>&1
```

# env
python 3

# package install
```
pip3 install -r requirements.txt
```
또는
```
pip3 install pymysql
pip3 install requests
pip3 install bs4
pip3 install regex
pip3 install urllib3
pip3 install openpyxl
pip3 install config
```
