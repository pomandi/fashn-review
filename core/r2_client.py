"""
R2 Client - Handles Cloudflare R2 operations for fabric images
"""

import os
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from typing import List, Dict, Optional

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', '.env'))


class R2Client:
    """Cloudflare R2 operations for fabric image management"""

    def __init__(self):
        self.account_id = os.environ["R2_ACCOUNT_ID"]
        self.access_key = os.environ["R2_ACCESS_KEY_ID"]
        self.secret_key = os.environ["R2_SECRET_ACCESS_KEY"]
        self.endpoint = os.getenv("R2_ENDPOINT", f"https://{self.account_id}.r2.cloudflarestorage.com")
        self.bucket_name = os.getenv("R2_BUCKET_NAME", "pomandi-media")
        self.public_url = os.environ["R2_PUBLIC_URL"]

        self.client = boto3.client(
            's3',
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name='auto'
        )

    def _get_public_url(self, key: str) -> str:
        """Get public CDN URL for an R2 object"""
        return f"{self.public_url}/{key}"

    def list_fabric_folders(self, prefix: str = "mtm-collection/") -> List[Dict]:
        """List all fabric collection folders"""
        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                Delimiter='/'
            )

            folders = []
            for cp in response.get('CommonPrefixes', []):
                folder_path = cp['Prefix']
                folder_name = folder_path.rstrip('/').split('/')[-1]
                # Skip non-fabric folders
                if folder_name in ('shirt-book-1', 'shirt-book-2', 'shirt-book-3',
                                   '1-lining-satin-book-1-button-book'):
                    continue
                folders.append({
                    'path': folder_path,
                    'name': folder_name,
                    'display_name': folder_name.replace('-', ' ').title()
                })

            return sorted(folders, key=lambda x: x['name'])

        except ClientError as e:
            print(f"R2 list folders error: {e}")
            return []

    def list_fabrics_in_folder(self, folder_path: str) -> List[Dict]:
        """List all fabric images in a specific folder"""
        try:
            fabrics = []
            continuation_token = None

            while True:
                kwargs = {
                    'Bucket': self.bucket_name,
                    'Prefix': folder_path,
                }
                if continuation_token:
                    kwargs['ContinuationToken'] = continuation_token

                response = self.client.list_objects_v2(**kwargs)

                for obj in response.get('Contents', []):
                    key = obj['Key']
                    filename = key.split('/')[-1]

                    # Skip non-image files and empty keys
                    if not filename or not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                        continue

                    fabric_code = filename.rsplit('.', 1)[0]

                    fabrics.append({
                        'key': key,
                        'filename': filename,
                        'code': fabric_code,
                        'url': self._get_public_url(key),
                        'size': obj['Size'],
                        'folder': folder_path.rstrip('/').split('/')[-1]
                    })

                if response.get('IsTruncated'):
                    continuation_token = response['NextContinuationToken']
                else:
                    break

            return sorted(fabrics, key=lambda x: x['code'])

        except ClientError as e:
            print(f"R2 list fabrics error: {e}")
            return []

    def list_all_fabrics(self, prefix: str = "mtm-collection/") -> Dict:
        """List all fabrics grouped by folder"""
        folders = self.list_fabric_folders(prefix)
        result = {}

        for folder in folders:
            fabrics = self.list_fabrics_in_folder(folder['path'])
            if fabrics:
                result[folder['name']] = {
                    'display_name': folder['display_name'],
                    'fabrics': fabrics,
                    'count': len(fabrics)
                }

        return result
