#!/usr/bin/env python
"""
Batch Product Image Generator
- Reads products from collection
- Generates AI images for each product using FASHN API
- Uploads generated images to Saleor product media

Usage:
    python batch-product-image-generator.py --preview     # Preview only, no generation
    python batch-product-image-generator.py --generate    # Generate images
    python batch-product-image-generator.py --limit 5     # Generate for first 5 products only
"""

import os
import sys
import json
import time
import argparse
import requests
import io
from datetime import datetime
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fashn import Fashn
from core.s3_client import S3Client

load_dotenv()

# Configuration
SALEOR_URL = "https://saleor-5f11a4761db9.herokuapp.com/graphql/"
FASHN_API_KEY = os.getenv("FASHN_API_KEY")

# Saleor token - get fresh one
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


class BatchProductImageGenerator:
    """Generate and upload images for products in batch"""

    def __init__(self):
        self.fashn = Fashn(api_key=FASHN_API_KEY)
        self.s3 = S3Client()
        self.token = get_fresh_token()
        self.results = []

        # Prompt for image generation - PEAKY BLINDERS STYLE
        self.prompt = """
        Tall elegant man in 1920s Peaky Blinders gangster style, Birmingham England aesthetic.
        Wearing a classic flat cap (newsboy cap), standing confidently with full body visible.
        Sharp features, period-accurate grooming. Powerful commanding pose.
        Dark moody industrial Birmingham background, vintage brick walls, cobblestone streets.
        Dramatic noir lighting with deep shadows, sepia-toned vintage photography style.
        Post-WWI era fashion editorial, cinematic film still quality, BBC period drama aesthetic.
        Atmospheric fog, golden hour warm tones mixed with cool shadows.
        """

    def _saleor_request(self, query, variables=None):
        """Execute Saleor GraphQL request"""
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
        response = requests.post(SALEOR_URL, json={'query': query, 'variables': variables or {}}, headers=headers)
        return response.json()

    def load_products(self, json_path):
        """Load products from JSON file"""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['products']

    def generate_image(self, product_id, product_name, source_image_url, callback=None):
        """Generate image using FASHN API"""
        if callback:
            callback(f"Generating image for: {product_name}")

        inputs = {
            "product_image": source_image_url,
            "prompt": self.prompt.strip().replace('\n', ' '),
            "aspect_ratio": "4:5",
            "resolution": "4k",
            "num_images": 1,
            "output_format": "png",
        }

        try:
            result = self.fashn.predictions.subscribe(
                model_name="product-to-model",
                inputs=inputs,
                on_enqueued=lambda pid: callback(f"  Queued: {pid}") if callback else None,
                on_queue_update=lambda status: callback(f"  Status: {status.status}") if callback else None,
            )

            if result.status == "completed" and result.output:
                fashn_url = result.output[0] if isinstance(result.output, list) else result.output
                if callback:
                    callback(f"  Generated: {fashn_url[:60]}...")
                return fashn_url
            else:
                if callback:
                    callback(f"  Failed: {getattr(result, 'error', 'Unknown error')}")
                return None

        except Exception as e:
            if callback:
                callback(f"  Error: {str(e)}")
            return None

    def upload_to_s3(self, fashn_url, product_slug, callback=None):
        """Upload generated image to S3"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{product_slug}_{timestamp}.png"

        s3_url = self.s3.upload_from_url(
            image_url=fashn_url,
            folder="fashn-api/product-images",
            filename=filename
        )

        if callback:
            callback(f"  S3: {s3_url[:60]}...")

        return s3_url

    def get_product_media_ids(self, product_id):
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
        data = self._saleor_request(query, {"id": product_id})
        media_list = data.get('data', {}).get('product', {}).get('media', [])
        return [m['id'] for m in media_list]

    def reorder_media_to_first(self, product_id, new_media_id, callback=None):
        """Reorder media so the new image is first (main image)"""
        # Get all current media IDs
        all_media_ids = self.get_product_media_ids(product_id)

        # Put new media first, then the rest
        if new_media_id in all_media_ids:
            all_media_ids.remove(new_media_id)
        new_order = [new_media_id] + all_media_ids

        # Call reorder mutation
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

        data = self._saleor_request(mutation, {"productId": product_id, "mediaIds": new_order})
        result = data.get('data', {}).get('productMediaReorder', {})

        if result.get('errors'):
            if callback:
                callback(f"  Reorder error: {result['errors']}")
            return False

        if callback:
            callback(f"  Set as main image (first position)")
        return True

    def add_to_saleor_product(self, product_id, image_url, alt_text, callback=None):
        """Add image to Saleor product using multipart upload"""
        if callback:
            callback(f"  Uploading to Saleor...")

        # Download image first
        response = requests.get(image_url)
        if response.status_code != 200:
            if callback:
                callback(f"  Failed to download image: {response.status_code}")
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

        headers = {"Authorization": f"Bearer {self.token}"}
        resp = requests.post(SALEOR_URL, files=files, headers=headers)

        if resp.status_code != 200:
            if callback:
                callback(f"  Saleor upload failed: {resp.status_code}")
            return None

        data = resp.json()
        if 'errors' in data:
            if callback:
                callback(f"  GraphQL error: {data['errors']}")
            return None

        result = data.get('data', {}).get('productMediaCreate', {})
        if result.get('errors'):
            if callback:
                callback(f"  Mutation error: {result['errors']}")
            return None

        media = result.get('media', {})
        if callback:
            callback(f"  Added to Saleor: {media.get('id')}")

        # REORDER: Set new image as first (main image)
        if media.get('id'):
            self.reorder_media_to_first(product_id, media['id'], callback)

        return media

    def process_product(self, product, callback=None):
        """Process a single product: generate + upload"""
        product_id = product['id']
        product_name = product['name']
        product_slug = product['slug']
        source_image = product['first_image']

        if not source_image:
            if callback:
                callback(f"SKIP: {product_name} - No source image")
            return {'status': 'skipped', 'reason': 'no_source_image'}

        if callback:
            callback(f"\n{'='*60}")
            callback(f"Processing: {product_name}")
            callback(f"{'='*60}")

        # Step 1: Generate image
        fashn_url = self.generate_image(product_id, product_name, source_image, callback)
        if not fashn_url:
            return {'status': 'failed', 'step': 'generation'}

        # Step 2: Upload to S3
        s3_url = self.upload_to_s3(fashn_url, product_slug, callback)
        if not s3_url:
            return {'status': 'failed', 'step': 's3_upload'}

        # Step 3: Add to Saleor product
        alt_text = f"AI generated image for {product_name}"
        media = self.add_to_saleor_product(product_id, s3_url, alt_text, callback)
        if not media:
            return {'status': 'failed', 'step': 'saleor_upload'}

        return {
            'status': 'success',
            'product_id': product_id,
            'product_name': product_name,
            'fashn_url': fashn_url,
            's3_url': s3_url,
            'saleor_media_id': media.get('id'),
            'saleor_media_url': media.get('url')
        }

    def run_batch(self, products, limit=None, callback=None):
        """Run batch processing for all products"""
        if limit:
            products = products[:limit]

        total = len(products)
        if callback:
            callback(f"\n{'#'*60}")
            callback(f"BATCH PROCESSING: {total} products")
            callback(f"{'#'*60}")

        results = []
        for i, product in enumerate(products):
            if callback:
                callback(f"\n[{i+1}/{total}]")

            result = self.process_product(product, callback)
            result['index'] = i + 1
            results.append(result)

            # Delay between products to avoid rate limiting
            if i < total - 1:
                time.sleep(2)

        # Summary
        success = len([r for r in results if r['status'] == 'success'])
        failed = len([r for r in results if r['status'] == 'failed'])
        skipped = len([r for r in results if r['status'] == 'skipped'])

        if callback:
            callback(f"\n\n{'='*60}")
            callback(f"BATCH COMPLETE")
            callback(f"{'='*60}")
            callback(f"Total: {total}")
            callback(f"Success: {success}")
            callback(f"Failed: {failed}")
            callback(f"Skipped: {skipped}")
            callback(f"Estimated Cost: ${total * 0.075:.2f}")

        # Save results
        results_path = f"output/batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        if callback:
            callback(f"\nResults saved to: {results_path}")

        return results


def print_callback(msg):
    print(msg)


def main():
    parser = argparse.ArgumentParser(description='Batch Product Image Generator')
    parser.add_argument('--preview', action='store_true', help='Preview products only, no generation')
    parser.add_argument('--generate', action='store_true', help='Generate images and upload')
    parser.add_argument('--limit', type=int, help='Limit number of products to process')
    parser.add_argument('--input', default='output/collection_products.json', help='Input JSON file')

    args = parser.parse_args()

    generator = BatchProductImageGenerator()
    products = generator.load_products(args.input)

    if args.preview or not args.generate:
        print(f"\n{'='*60}")
        print("PREVIEW MODE - Products to process:")
        print(f"{'='*60}\n")

        limit = args.limit or len(products)
        for i, p in enumerate(products[:limit]):
            status = "OK" if p['first_image'] else "NO IMAGE"
            print(f"{i+1}. [{status}] {p['name']}")
            print(f"   ID: {p['id']}")
            if p['first_image']:
                print(f"   Source: {p['first_image'][:60]}...")
            print()

        print(f"{'='*60}")
        print(f"Total: {len(products)} products")
        print(f"With images: {len([p for p in products if p['first_image']])}")
        print(f"Estimated cost: ${len(products[:limit]) * 0.075:.2f}")
        print(f"\nRun with --generate to start processing")

    elif args.generate:
        print(f"\n{'#'*60}")
        print("STARTING BATCH GENERATION")
        print(f"{'#'*60}")

        results = generator.run_batch(products, limit=args.limit, callback=print_callback)


if __name__ == "__main__":
    main()
