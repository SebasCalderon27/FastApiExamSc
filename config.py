import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_VIDEOS_BUCKET = os.getenv("S3_VIDEOS_BUCKET")
S3_THUMBNAILS_BUCKET = os.getenv("S3_THUMBNAILS_BUCKET")

