from io import BytesIO
from typing import Iterator

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from base64 import b64decode
import boto3

from config import S3_CONFIG


def replace_table(content: str, board, article_id: int) -> str:
    # s3 설정
    s3 = boto3.client(
        service_name='s3',
        aws_access_key_id=S3_CONFIG['aws_access_key_id'],
        aws_secret_access_key=S3_CONFIG['aws_secret_access_key'],
    )

    # Chrome 드라이버 설정
    options = Options()

    # 리눅스 환경에서만 활성화 - 셀레니움 GUI off
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--start-maximized")
    options.add_argument("--lang=ko_KR.UTF-8")

    options.add_argument("disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    driver.set_window_size(3840, 2160)

    images = capture_table(driver, s3, content, f'articles/{board.s3}/{article_id}')

    content = BeautifulSoup(content, 'html.parser')
    tables = content.select('table')

    for table, image in zip(tables, images):
        if not image:
            table.replace_with('')
            continue
        img_tag = content.new_tag('img', src=image)
        img_tag['style'] = "max-width: 100%;"

        table.replace_with(img_tag)

    driver.quit()
    return str(content)


def capture_table(driver, s3, content, s3_directory: str) -> Iterator[str]:
    driver.get('about:blank')

    driver.execute_script(f"document.documentElement.innerHTML = arguments[0];", content)

    selector = 'table'

    WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
    )

    tables = driver.find_elements(By.CSS_SELECTOR, selector)

    for i, table in enumerate(tables):
        clip = {k: v for k, v in list(table.location.items()) + list(table.size.items())}
        clip['scale'] = 1

        if clip['height'] <= 0 or clip['width'] <= 0:
            yield ''
            continue

        args = {
            "clip": clip,
            "captureBeyondViewport": True  # 얘가 True여야 안짤리고 캡쳐 가능
        }

        screenshot = driver.execute_cdp_cmd("Page.captureScreenshot", cmd_args=args)
        image = b64decode(screenshot['data'])

        yield upload_image(s3, f"{s3_directory}/{i}.png", image)


def upload_image(s3, file_name: str, image: bytes) -> str:
    try:
        s3.upload_fileobj(
            Fileobj=BytesIO(image),
            Bucket=S3_CONFIG['bucket'],
            Key=file_name,
            ExtraArgs={
                'ContentType': 'image/png',
                'ACL': 'public-read'
            }
        )
    except Exception as e:
        print(e)

    return f'{S3_CONFIG["upload_domain"]}/{file_name}'


def upload_txt(file_name: str, text_content: str) -> str:
    s3 = boto3.client(
        service_name='s3',
        aws_access_key_id=S3_CONFIG['aws_access_key_id'],
        aws_secret_access_key=S3_CONFIG['aws_secret_access_key'],
    )
    encoded_text = text_content.encode('utf-8')

    try:
        s3.upload_fileobj(
            Fileobj=BytesIO(encoded_text),
            Bucket=S3_CONFIG['bucket'],
            Key=file_name,
            ExtraArgs={
                'ContentType': 'text/plain; charset=utf-8',
                'ACL': 'public-read'
            }
        )
    except Exception as e:
        print(e)

    return f'{S3_CONFIG["upload_domain"]}/{file_name}'
