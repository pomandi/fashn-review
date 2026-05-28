#!/usr/bin/env python
"""Query products in a collection for image generation"""

import requests
import json

TOKEN = 'eyJhbGciOiJSUzI1NiIsImtpZCI6InZ3Ml9KVktyRHhqODM4MlYyYXp3aE0yMThDSVZTNV95NlYtWWVmdDdhdzgiLCJ0eXAiOiJKV1QifQ.eyJpYXQiOjE3NjU3NDgxMTAsIm93bmVyIjoic2FsZW9yIiwiaXNzIjoiaHR0cHM6Ly9zYWxlb3ItNWYxMWE0NzYxZGI5Lmhlcm9rdWFwcC5jb20vZ3JhcGhxbC8iLCJleHAiOjE3NjU3NTA4MTAsInRva2VuIjoiZnBqRXdvZWhBa0pLIiwiZW1haWwiOiJudXJ1bGxhaF9jZXZpazE5ODlAaG90bWFpbC5jb20iLCJ0eXBlIjoiYWNjZXNzIiwidXNlcl9pZCI6IlZYTmxjam94IiwiaXNfc3RhZmYiOnRydWV9.XK69RWQC7vg1O45w8fMz-d0vNQRbBdr1_HtugN-KpHMyaFWn_Oo9_41xi5ULMibe6zA6mUd146BjNZrKqYCkajub1STYNyKgSyD98on2Si06U5IJlEoKNCnLfnHaOIABhq8WPHlPMf-ztyjN09KHT_tOifXz3MjOO7iOORPID6zFe-43TEf7m92h5Cw6es7c7leJRAJt5aJiaPqgJvzj9kv7wRbVA70dbqf16tAVAkfDsysj9VZqBjLrU5i3Ur944yKEKHauvRLtRCe8lWuqN3EmnrmXgoovcgAHn_Tf3m4Guo-fPgITd9WuWLEybPcB53Is4yGHPseiliv4SejCPg'

headers = {
    'Authorization': f'Bearer {TOKEN}',
    'Content-Type': 'application/json'
}

# Collection ID from URL: Q29sbGVjdGlvbjoxNjg= (base64 decoded = Collection:168)
collection_id = 'Q29sbGVjdGlvbjoxNjg='

query = """
query GetCollectionProducts($id: ID!, $first: Int!) {
    collection(id: $id) {
        id
        name
        slug
        products(first: $first) {
            edges {
                node {
                    id
                    name
                    slug
                    media {
                        id
                        url
                        alt
                    }
                }
            }
        }
    }
}
"""

response = requests.post(
    'https://saleor-5f11a4761db9.herokuapp.com/graphql/',
    json={'query': query, 'variables': {'id': collection_id, 'first': 50}},
    headers=headers
)

data = response.json()

if 'errors' in data:
    print('ERRORS:', json.dumps(data['errors'], indent=2))
else:
    collection = data['data'].get('collection')
    if collection:
        print(f'Collection: {collection["name"]} ({collection["slug"]})')
        print(f'ID: {collection["id"]}')
        print()

        products = collection.get('products', {}).get('edges', [])
        print(f'Total Products: {len(products)}')
        print('=' * 80)

        # Save products data for later use
        products_data = []

        for i, edge in enumerate(products):
            p = edge['node']
            media = p.get('media', [])
            first_image = media[0]['url'] if media else None

            product_info = {
                'id': p['id'],
                'name': p['name'],
                'slug': p['slug'],
                'first_image': first_image,
                'total_images': len(media)
            }
            products_data.append(product_info)

            print(f'{i+1}. {p["name"]}')
            print(f'   ID: {p["id"]}')
            print(f'   Images: {len(media)}')
            if first_image:
                display_url = first_image[:80] + '...' if len(first_image) > 80 else first_image
                print(f'   First: {display_url}')
            else:
                print(f'   First: NO IMAGE')
            print()

        # Save to JSON for batch processing
        with open('output/collection_products.json', 'w', encoding='utf-8') as f:
            json.dump({
                'collection': {
                    'id': collection['id'],
                    'name': collection['name'],
                    'slug': collection['slug']
                },
                'products': products_data
            }, f, indent=2, ensure_ascii=False)

        print('=' * 80)
        print(f'Saved to output/collection_products.json')
        print(f'Products with images: {len([p for p in products_data if p["first_image"]])}')
        print(f'Products without images: {len([p for p in products_data if not p["first_image"]])}')
    else:
        print('Collection not found!')
        print(json.dumps(data, indent=2))
