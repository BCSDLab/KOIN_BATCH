import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / '.env')

DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST', ''),
    'port': int(os.getenv('DB_PORT', '3306')),
    'db': os.getenv('DB_NAME', ''),
    'user': os.getenv('DB_USER', ''),
    'password': os.getenv('DB_PASSWORD', ''),
}

MYSQL_CONFIG = DATABASE_CONFIG

MONGO_CONFIG = {
    'host': os.getenv('MONGO_HOST', ''),
    'port': int(os.getenv('MONGO_PORT', '27017')),
    'db': os.getenv('MONGO_DB', ''),
    'user': os.getenv('MONGO_USER', ''),
    'password': os.getenv('MONGO_PASSWORD', ''),
}

REDIS_CONFIG = {
    'host': os.getenv('REDIS_HOST', ''),
    'port': int(os.getenv('REDIS_PORT', '0')),
    'db': os.getenv('REDIS_DB', ''),
    'password': os.getenv('REDIS_PASSWORD', ''),
}

PORTAL_CONFIG = {
    'id': os.getenv('PORTAL_ID', ''),
    'pw': os.getenv('PORTAL_PW', ''),
    'ip': os.getenv('PORTAL_IP', ''),
}

GMAIL_CONFIG = {
    'id': os.getenv('GMAIL_ID', ''),
    'pw': os.getenv('GMAIL_PW', ''),
}

SLACK_CONFIG = {
    'url': os.getenv('SLACK_WEBHOOK_URL', ''),
}

S3_CONFIG = {
    'aws_access_key_id': os.getenv('S3_ACCESS_KEY_ID', ''),
    'aws_secret_access_key': os.getenv('S3_SECRET_ACCESS_KEY', ''),
    'bucket': os.getenv('S3_BUCKET', ''),
    'upload_domain': os.getenv('S3_UPLOAD_DOMAIN', ''),
}

BATCH_CONFIG = {
    'email': os.getenv('BATCH_EMAIL', ''),
    'password': os.getenv('BATCH_PASSWORD', ''),
    'token_url': os.getenv('BATCH_TOKEN_URL', ''),
    'notification_api_url': os.getenv('BATCH_NOTIFICATION_API_URL', ''),
}
