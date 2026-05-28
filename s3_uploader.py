"""
S3 Uploader for FASHN API images
Uploads base model and generated images to S3
"""

import os
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
import requests
from datetime import datetime

load_dotenv()

AWS_ACCESS_KEY_ID = os.environ["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
AWS_BUCKET_NAME = os.getenv("AWS_S3_BUCKET", "saleorme")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# S3 Folders
BASE_MODELS_FOLDER = "fashn-api/base-models"
GENERATED_IMAGES_FOLDER = "fashn-api/new-collection-images"


def get_s3_client():
    """Create S3 client"""
    return boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )


def upload_file_to_s3(local_path: str, s3_folder: str, filename: str = None) -> str:
    """
    Upload a local file to S3

    Args:
        local_path: Local file path
        s3_folder: S3 folder path (without bucket name)
        filename: Optional custom filename

    Returns:
        Public S3 URL
    """
    s3 = get_s3_client()

    if filename is None:
        filename = os.path.basename(local_path)

    s3_key = f"{s3_folder}/{filename}"

    # Determine content type
    ext = filename.lower().split('.')[-1]
    content_types = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'webp': 'image/webp'
    }
    content_type = content_types.get(ext, 'image/jpeg')

    try:
        s3.upload_file(
            local_path,
            AWS_BUCKET_NAME,
            s3_key,
            ExtraArgs={
                'ContentType': content_type
            }
        )

        url = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
        print(f"Uploaded: {url}")
        return url

    except ClientError as e:
        print(f"Upload error: {e}")
        return None


def upload_url_to_s3(image_url: str, s3_folder: str, filename: str) -> str:
    """
    Download image from URL and upload to S3

    Args:
        image_url: Source image URL
        s3_folder: S3 folder path
        filename: Target filename

    Returns:
        Public S3 URL
    """
    s3 = get_s3_client()

    # Download image
    response = requests.get(image_url)
    response.raise_for_status()

    s3_key = f"{s3_folder}/{filename}"

    # Determine content type
    ext = filename.lower().split('.')[-1]
    content_types = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'webp': 'image/webp'
    }
    content_type = content_types.get(ext, 'image/jpeg')

    try:
        s3.put_object(
            Bucket=AWS_BUCKET_NAME,
            Key=s3_key,
            Body=response.content,
            ContentType=content_type
        )

        url = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
        print(f"Uploaded from URL: {url}")
        return url

    except ClientError as e:
        print(f"Upload error: {e}")
        return None


def upload_base_model(local_path: str, model_name: str = "dutch-blond-model") -> str:
    """Upload base model image to S3"""
    ext = local_path.split('.')[-1]
    filename = f"{model_name}.{ext}"
    return upload_file_to_s3(local_path, BASE_MODELS_FOLDER, filename)


def upload_generated_image(image_url: str, collection_slug: str) -> str:
    """
    Download generated image from FASHN CDN and upload to S3

    Args:
        image_url: FASHN CDN URL
        collection_slug: Collection slug for naming

    Returns:
        Public S3 URL
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{collection_slug}_{timestamp}.png"
    return upload_url_to_s3(image_url, GENERATED_IMAGES_FOLDER, filename)


def list_s3_folder(folder: str):
    """List files in S3 folder"""
    s3 = get_s3_client()

    try:
        response = s3.list_objects_v2(
            Bucket=AWS_BUCKET_NAME,
            Prefix=folder
        )

        if 'Contents' in response:
            print(f"\nFiles in {folder}:")
            for obj in response['Contents']:
                print(f"  - {obj['Key']}")
        else:
            print(f"\nNo files in {folder}")

    except ClientError as e:
        print(f"List error: {e}")


if __name__ == "__main__":
    # Test: Upload base model
    BASE_MODEL_PATH = r"C:\software-project\sale-v2\fashn-api\full_body_front_view_photograph_of_a.jpeg"

    print("=" * 60)
    print("S3 Uploader Test")
    print("=" * 60)

    if os.path.exists(BASE_MODEL_PATH):
        print(f"\nUploading base model: {BASE_MODEL_PATH}")
        url = upload_base_model(BASE_MODEL_PATH)
        if url:
            print(f"\nBase model URL: {url}")
    else:
        print(f"File not found: {BASE_MODEL_PATH}")

    # List folders
    list_s3_folder(BASE_MODELS_FOLDER)
    list_s3_folder(GENERATED_IMAGES_FOLDER)
