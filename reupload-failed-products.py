#!/usr/bin/env python
"""
Re-upload failed products from S3 to Saleor
Products 29-35 that failed due to token expiration during batch processing
"""

import os
import sys
import json
import requests
import io
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.s3_client import S3Client

# Configuration
SALEOR_URL = "https://saleor-5f11a4761db9.herokuapp.com/graphql/"

# Failed products (index 29-35)
FAILED_PRODUCTS = [
    {
        "index": 29,
        "id": "UHJvZHVjdDo3ODM=",
        "name": "Light Gray Checkered Three-Piece Suit with Bow Tie",
        "slug": "lichtblauw-pak-3-c334d38f"
    },
    {
        "index": 30,
        "id": "UHJvZHVjdDo3OTE=",
        "name": "Gray Checkered Suit with Bronze Accents",
        "slug": "lichtgrijs-geruit-design-pak-bc013ed2"
    },
    {
        "index": 31,
        "id": "UHJvZHVjdDo3Mzg=",
        "name": "Navy Blue Plaid Suit with Paisley Tie",
        "slug": "navi-blauw-geruit-design-pak-3-delig-930393b9"
    },
    {
        "index": 32,
        "id": "UHJvZHVjdDo4MTk=",
        "name": "Burgundy Checkered Suit with Leaf Patterned Tie",
        "slug": "oud-roze-trouwpak-3be079af"
    },
    {
        "index": 33,
        "id": "UHJvZHVjdDo4MjI=",
        "name": "Light Blue Checked Three-Piece Suit",
        "slug": "pk-238-pastelblauw-kostuum-4a69a892"
    },
    {
        "index": 34,
        "id": "UHJvZHVjdDo3MTk=",
        "name": "Rich Burgundy Checkered Suit with Paisley Tie",
        "slug": "pk-513-bordeaux-rood-pak-af0bfcd6"
    },
    {
        "index": 35,
        "id": "UHJvZHVjdDo4MjE=",
        "name": "Burgundy Checkered Three-Piece Suit with Bow Tie",
        "slug": "roze-trouwpak-fc61f1ee"
    }
]


def get_fresh_token():
    """Get a fresh Saleor access token"""
    mutation = """
    mutation {
      tokenCreate(email: "nurullah_cevik1989@hotmail.com", password: "123456") {
        token
        errors { field message }
      }
    }
    """
    response = requests.post(SALEOR_URL, json={'query': mutation}, headers={'Content-Type': 'application/json'})
    data = response.json()
    if data.get('data', {}).get('tokenCreate', {}).get('token'):
        return data['data']['tokenCreate']['token']
    raise Exception(f"Failed to get token: {data}")


def saleor_request(token, query, variables=None):
    """Execute Saleor GraphQL request"""
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    response = requests.post(SALEOR_URL, json={'query': query, 'variables': variables or {}}, headers=headers)
    return response.json()


def get_product_media_ids(token, product_id):
    """Get all media IDs for a product"""
    query = """
    query GetProductMedia($id: ID!) {
        product(id: $id) {
            media {
                id
            }
        }
    }
    """
    data = saleor_request(token, query, {"id": product_id})
    media_list = data.get('data', {}).get('product', {}).get('media', [])
    return [m['id'] for m in media_list]


def reorder_media_to_first(token, product_id, new_media_id):
    """Reorder media so the new image is first (main image)"""
    all_media_ids = get_product_media_ids(token, product_id)

    if new_media_id in all_media_ids:
        all_media_ids.remove(new_media_id)
    new_order = [new_media_id] + all_media_ids

    mutation = """
    mutation ProductMediaReorder($productId: ID!, $mediaIds: [ID!]!) {
        productMediaReorder(productId: $productId, mediaIds: $mediaIds) {
            product {
                id
                media {
                    id
                    sortOrder
                }
            }
            errors {
                field
                message
            }
        }
    }
    """

    data = saleor_request(token, mutation, {"productId": product_id, "mediaIds": new_order})
    result = data.get('data', {}).get('productMediaReorder', {})

    if result.get('errors'):
        print(f"  Reorder error: {result['errors']}")
        return False

    print(f"  Set as main image (first position)")
    return True


def add_to_saleor_product(token, product_id, image_url, alt_text):
    """Add image to Saleor product using multipart upload"""
    print(f"  Uploading to Saleor...")

    # Download image first
    response = requests.get(image_url)
    if response.status_code != 200:
        print(f"  Failed to download image: {response.status_code}")
        return None

    image_content = response.content

    # Prepare multipart GraphQL request
    operations = {
        "query": """
            mutation ProductMediaCreate($product: ID!, $image: Upload!, $alt: String) {
                productMediaCreate(input: {
                    product: $product,
                    image: $image,
                    alt: $alt
                }) {
                    media {
                        id
                        url
                        alt
                    }
                    errors {
                        field
                        message
                        code
                    }
                }
            }
        """,
        "variables": {
            "product": product_id,
            "image": None,
            "alt": alt_text
        }
    }

    map_data = {"0": ["variables.image"]}
    filename = image_url.split('/')[-1] or "image.png"

    files = {
        'operations': (None, json.dumps(operations), 'application/json'),
        'map': (None, json.dumps(map_data), 'application/json'),
        '0': (filename, io.BytesIO(image_content), 'image/png')
    }

    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(SALEOR_URL, files=files, headers=headers)

    if resp.status_code != 200:
        print(f"  Saleor upload failed: {resp.status_code}")
        return None

    data = resp.json()
    if 'errors' in data:
        print(f"  GraphQL error: {data['errors']}")
        return None

    result = data.get('data', {}).get('productMediaCreate', {})
    if result.get('errors'):
        print(f"  Mutation error: {result['errors']}")
        return None

    media = result.get('media', {})
    print(f"  Added to Saleor: {media.get('id')}")

    # REORDER: Set new image as first (main image)
    if media.get('id'):
        reorder_media_to_first(token, product_id, media['id'])

    return media


def list_s3_files(s3_client, prefix):
    """List all files in S3 with given prefix"""
    import boto3

    s3 = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name='us-east-1'
    )

    bucket = os.getenv('AWS_S3_BUCKET_NAME', 'saleorme')

    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    files = []

    if 'Contents' in response:
        for obj in response['Contents']:
            files.append({
                'key': obj['Key'],
                'url': f"https://{bucket}.s3.us-east-1.amazonaws.com/{obj['Key']}",
                'last_modified': obj['LastModified']
            })

    return files


def find_s3_url_for_product(s3_files, slug):
    """Find S3 URL for a product based on slug"""
    for f in s3_files:
        if slug in f['key']:
            return f['url']
    return None


def main():
    from dotenv import load_dotenv
    load_dotenv()

    print("=" * 60)
    print("RE-UPLOAD FAILED PRODUCTS TO SALEOR")
    print("=" * 60)

    # Get fresh token
    print("\n[1] Getting fresh Saleor token...")
    token = get_fresh_token()
    print("   Token obtained successfully!")

    # List S3 files
    print("\n[2] Listing S3 files...")
    s3_client = S3Client()
    s3_files = list_s3_files(s3_client, "fashn-api/product-images/")
    print(f"   Found {len(s3_files)} files in S3")

    # Show available files
    print("\n   Available S3 files (last 10):")
    for f in s3_files[-10:]:
        print(f"   - {f['key'].split('/')[-1]}")

    # Process each failed product
    print("\n[3] Processing failed products...")
    results = []

    for product in FAILED_PRODUCTS:
        print(f"\n{'='*60}")
        print(f"[{product['index']}/35] {product['name']}")
        print(f"{'='*60}")

        # Find S3 URL
        s3_url = find_s3_url_for_product(s3_files, product['slug'])

        if not s3_url:
            print(f"  WARNING: No S3 file found for slug: {product['slug']}")
            # Try partial match
            slug_parts = product['slug'].split('-')
            for part in slug_parts[:3]:
                for f in s3_files:
                    if part in f['key'] and part not in ['pak', 'geruit', '3']:
                        s3_url = f['url']
                        print(f"  Found partial match: {f['key'].split('/')[-1]}")
                        break
                if s3_url:
                    break

        if not s3_url:
            print(f"  SKIP: Could not find S3 file")
            results.append({
                'index': product['index'],
                'status': 'skipped',
                'reason': 'no_s3_file'
            })
            continue

        print(f"  S3 URL: {s3_url[:60]}...")

        # Upload to Saleor
        alt_text = f"AI generated image for {product['name']}"
        media = add_to_saleor_product(token, product['id'], s3_url, alt_text)

        if media:
            results.append({
                'index': product['index'],
                'status': 'success',
                'product_id': product['id'],
                'product_name': product['name'],
                's3_url': s3_url,
                'saleor_media_id': media.get('id'),
                'saleor_media_url': media.get('url')
            })
        else:
            results.append({
                'index': product['index'],
                'status': 'failed',
                'reason': 'saleor_upload_failed'
            })

    # Summary
    success = len([r for r in results if r['status'] == 'success'])
    failed = len([r for r in results if r['status'] == 'failed'])
    skipped = len([r for r in results if r['status'] == 'skipped'])

    print(f"\n\n{'='*60}")
    print("RE-UPLOAD COMPLETE")
    print(f"{'='*60}")
    print(f"Total: {len(FAILED_PRODUCTS)}")
    print(f"Success: {success}")
    print(f"Failed: {failed}")
    print(f"Skipped: {skipped}")

    # Save results
    results_path = f"output/reupload_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {results_path}")


if __name__ == "__main__":
    main()
