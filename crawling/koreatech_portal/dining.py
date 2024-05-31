import requests
from login import portal_login

cookies = portal_login()
if cookies is None:
    print("식단 크롤링 실패 - 쿠키 없음")

KSMSID = cookies['__KSMSID__'] # 로그인 정보(쿠키에 있음)

eat_date = "20240530"  # 또는 "2024-05-30"
eat_type = "lunch"
restaurant = "한식"
campus = "Campus1"  # 2캠은 Campus2

body = f"""<?xml version="1.0" encoding="UTF-8"?>
<Root xmlns="http://www.nexacroplatform.com/platform/dataset">
    <Parameters>
        <Parameter id="method">getList_sp</Parameter>
        <Parameter id="sqlid">NK_COT_MEAL_PLAN.NP_SELECT_11</Parameter>
        <Parameter id="locale">ko</Parameter>
    </Parameters>
    <Dataset id="input1">
        <ColumnInfo>
            <Column id="CAMPUS" type="string" size="4000" />
            <Column id="RESTURANT" type="string" size="4000" />
            <Column id="EAT_DATE" type="string" size="4000" />
            <Column id="EAT_TYPE" type="string" size="4000" />
        </ColumnInfo>
        <Rows>
            <Row>
                <Col id="EAT_DATE">{eat_date}</Col>
                <Col id="EAT_TYPE">{eat_type}</Col>
                <Col id="RESTURANT">{restaurant}</Col>
                <Col id="CAMPUS">{campus}</Col>
            </Row>
        </Rows>
    </Dataset>
</Root>""".encode("utf-8")

headers = {"Content-Type": "text/xml; charset=utf-8"}
cookies = {"__KSMSID__": f"{KSMSID};Domain=koreatech.ac.kr;"}

response = requests.post(
    "https://kut90.koreatech.ac.kr/nexacroController.do",
    headers=headers,
    cookies=cookies,
    data=body
)

print(response.text)