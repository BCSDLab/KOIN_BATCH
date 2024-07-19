import crawling.config as config

import requests
from bs4 import BeautifulSoup

from datetime import datetime
from pytz import timezone

from functools import lru_cache
from pymongo import MongoClient, UpdateOne
from pymongo.errors import BulkWriteError
from bson.int64 import Int64

mongo_connection = None
KST = timezone('Asia/Seoul')


@lru_cache(maxsize=None)
def get_mongodb_connection():
    return MongoClient(
        host=config.MONGO_CONFIG["host"],
        port=config.MONGO_CONFIG["port"],
        username=config.MONGO_CONFIG["user"],
        password=config.MONGO_CONFIG["password"]
    )[config.MONGO_CONFIG["db"]]


class BusInfo:
    def __init__(self, route_info):
        self.number = Int64(route_info["ROUTE_NAME"])
        self.depart_node = route_info["ST_STOP_NAME"]
        self.arrival_node = route_info["ED_STOP_NAME"]

    def dict(self):
        return {
            'number': self.number,
            'depart_node': self.depart_node,
            'arrival_node': self.arrival_node
        }

    def __str__(self): return str(self.dict())

    def __repr__(self): return str(self)


class BusTimeTable:
    def __init__(self, day_of_week, depart_info):
        self.day_of_week = day_of_week
        self.depart_info = depart_info

    def dict(self):
        return {
            'day_of_week': self.day_of_week,
            'depart_info': self.depart_info
        }

    def __str__(self): return str(self.dict())

    def __repr__(self): return str(self)


class TimetableDocument:
    def __init__(self, updated_at, route_info, bus_timetables):
        self.route_id = route_info["ROUTE_ID"]
        self.updated_at = updated_at
        self.bus_info = BusInfo(route_info)
        self.bus_timetables = bus_timetables

    def dict(self):
        return {
            '_id': self.route_id,
            'updated_at': self.updated_at,
            'bus_info': self.bus_info.dict(),
            'bus_timetables': self.bus_timetables
        }

    def __str__(self): return str(self.dict())

    def __repr__(self): return str(self)


def get_available_bus():
    """
    open api 트래픽 초과로 redis에 버스 정보가 없음
    TODO open api 트래픽 초과 해결되면 redis에서 가져오기
    :return:
    """
    return [400, 402, 405]


def get_route_ids(bus_number):
    result_list = (
        requests
        .get(f"https://its.cheonan.go.kr/bis/getBusTimeTable.do?thisPage=1&searchKeyword={bus_number}")
        .json()
    )

    return list(map(lambda route: route["ROUTE_ID"], result_list["resultList"]))


def get_route_info(route_id):
    return (
        requests
        .get(f"https://its.cheonan.go.kr/bis/getRouteList.do?searchKeyword={route_id}")
        .json()
    )


def get_timetable(route_info):
    route_info = route_info["resultList"][0]
    route_name = route_info["ROUTE_NAME"]
    route_direction = route_info["ROUTE_DIRECTION"]
    relay_areacode = route_info["RELAY_AREACODE"]
    route_explain = route_info["ROUTE_EXPLAIN"]
    st_name = route_info["ST_STOP_NAME"]
    ed_name = route_info["ED_STOP_NAME"]
    url = f"https://its.cheonan.go.kr/bis/showBusTimeTable.do?routeName={route_name}&routeDirection={route_direction}&relayAreacode={relay_areacode}&routeExplain={route_explain}&stName={st_name}&edName={ed_name}"

    html = requests.get(url)
    soup = BeautifulSoup(html.text, "html.parser")

    timetables = []
    for idx, day_of_week in enumerate(("평일", "주말", "공휴일", "임시")):
        depart_info = soup.select(
            f"body > div.timeTalbeWrap > div > div.timeTable-wrap > div:nth-child({idx + 1}) > dl > dd")
        depart_info = list(map(lambda x: x.string[:5], depart_info))

        timetables.append(
            BusTimeTable(day_of_week, depart_info)
            .dict()
        )

    return (
        TimetableDocument(datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S'), route_info, timetables)
        .dict()
    )


def crawling():
    available_buses = get_available_bus()
    print(available_buses)

    route_ids = sum(map(get_route_ids, available_buses), [])
    print(route_ids)

    route_infos = list(map(get_route_info, route_ids))
    print(route_infos)

    timetables = list(map(get_timetable, route_infos))
    print(*timetables, sep="\n")

    return timetables


def main():
    timetables = crawling()

    # MongoDB 연결 및 컬렉션 선택
    db = get_mongodb_connection()
    collection = db['citybus_timetables']

    # 업데이트 작업 준비
    updates = [
        UpdateOne(
            {'_id': timetable['_id']},
            {'$set': timetable},
            upsert=True
        ) for timetable in timetables
    ]

    try:
        # unordered 방식으로 벌크 업데이트 실행
        result = collection.bulk_write(updates, ordered=False)
        print(f"Upserted: {result.upserted_count}, Modified: {result.modified_count}, Matched: {result.matched_count}")
    except BulkWriteError as bwe:
        print(f"Error occurred, but some operations might have succeeded.")
        print(
            f"Upserted: {bwe.details.get('nUpserted', 0)}, Modified: {bwe.details.get('nModified', 0)}, Matched: {bwe.details.get('nMatched', 0)}")
        print(f"Number of failures: {len(bwe.details.get('writeErrors', []))}")


if __name__ == '__main__':
    main()
