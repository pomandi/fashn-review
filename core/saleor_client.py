"""
Saleor Client - GraphQL integration for collections and products
Handles fetching entities and updating images after approval
"""

import os
import requests
import base64
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

load_dotenv()


class SaleorClient:
    """Client for Saleor GraphQL API"""

    def __init__(self):
        self.api_url = os.getenv("SALEOR_URL", "https://api.pomandi.com/graphql/")
        self.api_token = os.getenv("SALEOR_API_TOKEN")

        if not self.api_token:
            # Try loading from scripts env
            scripts_env = os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', '.envForScripts')
            if os.path.exists(scripts_env):
                with open(scripts_env, 'r') as f:
                    for line in f:
                        if line.startswith('SCRIPT_API_TOKEN='):
                            self.api_token = line.strip().split('=', 1)[1]
                            break

    def _execute(self, query: str, variables: dict = None) -> Dict[str, Any]:
        """Execute GraphQL query"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_token}"
        }

        response = requests.post(
            self.api_url,
            json={"query": query, "variables": variables or {}},
            headers=headers
        )

        if response.status_code != 200:
            raise Exception(f"GraphQL error: {response.status_code} - {response.text}")

        data = response.json()
        if "errors" in data:
            raise Exception(f"GraphQL errors: {data['errors']}")

        return data.get("data", {})

    def get_collections(self, channel: str = "benelux-b2c", first: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch all collections with their Saleor IDs

        Returns list of:
        {
            "id": "Q29sbGVjdGlvbjox",  # GraphQL ID - REQUIRED for updates
            "slug": "tuxedo",
            "name": "Tuxedo",
            "backgroundImage": { "url": "..." }
        }
        """
        # Use admin query without channel filter to get all collections
        query = """
        query GetCollections($first: Int!) {
            collections(first: $first) {
                edges {
                    node {
                        id
                        slug
                        name
                        backgroundImage {
                            url
                            alt
                        }
                        description
                    }
                }
            }
        }
        """

        data = self._execute(query, {"first": first})
        collections = []

        for edge in data.get("collections", {}).get("edges", []):
            node = edge["node"]
            collections.append({
                "id": node["id"],  # This is the GraphQL ID needed for mutations!
                "slug": node["slug"],
                "name": node["name"],
                "backgroundImage": node.get("backgroundImage"),
                "description": node.get("description")
            })

        return collections

    def get_collection_by_slug(self, slug: str, channel: str = "benelux-b2c") -> Optional[Dict[str, Any]]:
        """Get a single collection by slug"""
        query = """
        query GetCollection($slug: String!, $channel: String!) {
            collection(slug: $slug, channel: $channel) {
                id
                slug
                name
                backgroundImage {
                    url
                    alt
                }
            }
        }
        """

        data = self._execute(query, {"slug": slug, "channel": channel})
        collection = data.get("collection")

        if collection:
            return {
                "id": collection["id"],
                "slug": collection["slug"],
                "name": collection["name"],
                "backgroundImage": collection.get("backgroundImage")
            }
        return None

    def update_collection_background_image(
        self,
        collection_id: str,
        image_url: str,
        alt_text: str = None
    ) -> Dict[str, Any]:
        """
        Update collection background image

        Args:
            collection_id: Saleor GraphQL ID (e.g., "Q29sbGVjdGlvbjox")
            image_url: URL of the image to set (can be private S3 URL)
            alt_text: Optional alt text for the image

        Returns:
            Updated collection data
        """
        # Use multipart upload which handles private S3 files via AWS SDK
        return self._upload_collection_image(collection_id, image_url, alt_text)

    def _upload_collection_image(
        self,
        collection_id: str,
        image_url: str,
        alt_text: str = None
    ) -> Dict[str, Any]:
        """Upload image to collection using multipart form"""
        import io
        import json
        import boto3

        # Try direct download first
        response = requests.get(image_url)
        if response.status_code == 403:
            # Image is private in S3, use boto3 to download
            print(f"  Direct download failed (403), using AWS SDK...")
            s3_client = boto3.client(
                's3',
                aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
                aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
                region_name=os.getenv("AWS_REGION", "us-east-1"),
            )
            # Extract key from URL
            # URL format: https://saleorme.s3.us-east-1.amazonaws.com/path/to/file.png
            # or https://saleorme.s3.amazonaws.com/path/to/file.png
            bucket = "saleorme"
            if ".s3.us-east-1.amazonaws.com/" in image_url:
                key = image_url.split(".s3.us-east-1.amazonaws.com/")[1]
            elif ".s3.amazonaws.com/" in image_url:
                key = image_url.split(".s3.amazonaws.com/")[1]
            else:
                raise Exception(f"Cannot parse S3 URL: {image_url}")

            s3_obj = s3_client.get_object(Bucket=bucket, Key=key)
            image_content = s3_obj['Body'].read()
        elif response.status_code != 200:
            raise Exception(f"Failed to download image: {response.status_code}")
        else:
            image_content = response.content

        # Prepare multipart request
        operations = {
            "query": """
                mutation UpdateCollectionBackground($id: ID!, $backgroundImage: Upload, $backgroundImageAlt: String) {
                    collectionUpdate(
                        id: $id,
                        input: {
                            backgroundImage: $backgroundImage,
                            backgroundImageAlt: $backgroundImageAlt
                        }
                    ) {
                        collection {
                            id
                            slug
                            name
                            backgroundImage {
                                url
                                alt
                            }
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
                "id": collection_id,
                "backgroundImage": None,
                "backgroundImageAlt": alt_text or "AI generated collection image"
            }
        }

        map_data = {
            "0": ["variables.backgroundImage"]
        }

        # Determine filename from URL
        filename = image_url.split('/')[-1] or "image.png"

        files = {
            'operations': (None, json.dumps(operations), 'application/json'),
            'map': (None, json.dumps(map_data), 'application/json'),
            '0': (filename, io.BytesIO(image_content), 'image/png')
        }

        headers = {
            "Authorization": f"Bearer {self.api_token}"
        }

        resp = requests.post(self.api_url, files=files, headers=headers)

        if resp.status_code != 200:
            raise Exception(f"Upload failed: {resp.status_code} - {resp.text}")

        data = resp.json()
        if "errors" in data:
            raise Exception(f"GraphQL errors: {data['errors']}")

        result = data.get("data", {}).get("collectionUpdate", {})
        if result.get("errors"):
            raise Exception(f"Mutation errors: {result['errors']}")

        return result.get("collection", {})

    def get_products(self, channel: str = "benelux-b2c", first: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch products with their Saleor IDs

        Returns list of:
        {
            "id": "UHJvZHVjdDox",  # GraphQL ID
            "slug": "product-slug",
            "name": "Product Name",
            "thumbnail": { "url": "..." }
        }
        """
        query = """
        query GetProducts($channel: String!, $first: Int!) {
            products(channel: $channel, first: $first) {
                edges {
                    node {
                        id
                        slug
                        name
                        thumbnail {
                            url
                            alt
                        }
                    }
                }
            }
        }
        """

        data = self._execute(query, {"channel": channel, "first": first})
        products = []

        for edge in data.get("products", {}).get("edges", []):
            node = edge["node"]
            products.append({
                "id": node["id"],
                "slug": node["slug"],
                "name": node["name"],
                "thumbnail": node.get("thumbnail")
            })

        return products

    # ================================================================
    # FABRIC → PRODUCT CREATION METHODS
    # ================================================================

    # Saleor IDs
    PRODUCT_TYPE_SUIT = "UHJvZHVjdFR5cGU6NDk2"  # Kostuum heren
    CATEGORY_DEFAULT = "Q2F0ZWdvcnk6MQ=="
    CHANNELS = [
        {"id": "Q2hhbm5lbDox", "slug": "default-channel"},
        {"id": "Q2hhbm5lbDozNQ==", "slug": "belgium-channel"},
        {"id": "Q2hhbm5lbDozNA==", "slug": "netherlands-channel"},
    ]

    # Map fabric folder names to collection slugs/names
    FOLDER_TO_COLLECTION = {
        "new-1-super-100s": {"name": "New 1 Super 100s", "quality": "Super 100s"},
        "new-2-super-100s": {"name": "New 2 Super 100s", "quality": "Super 100s"},
        "new-3-super-100s": {"name": "New 3 Super 100s", "quality": "Super 100s"},
        "new-4-super-100s": {"name": "New 4 Super 100s", "quality": "Super 100s"},
        "new-5-super-110s": {"name": "New 5 Super 110s", "quality": "Super 110s"},
        "new-6-super-110s": {"name": "New 6 Super 110s", "quality": "Super 110s"},
        "new-7-super-130s": {"name": "New 7 Super 130s", "quality": "Super 130s"},
        "new-8-super-130s": {"name": "New 8 Super 130s", "quality": "Super 130s"},
        "new-9-super-130s": {"name": "New 9 Super 130s", "quality": "Super 130s"},
        "new.-10-linen-seersucher-stretchy": {"name": "Linen Seersucker Stretchy", "quality": "Linen Blend", "slug": "new-10-linen-seersucker-stretchy"},
        "new.-11-super-110-washable-stretchy": {"name": "Washable Stretchy Super 110", "quality": "Super 110s", "slug": "new-11-super-110-washable-stretchy"},
        "new.-12-cotton-corduroy": {"name": "Cotton Corduroy", "quality": "Cotton", "slug": "new-12-cotton-corduroy"},
        "new.-13-overcoat": {"name": "Overcoat Collection", "quality": "Overcoat", "slug": "new-13-overcoat"},
        "jacquard-no.-3": {"name": "Jacquard No. 3", "quality": "Jacquard", "slug": "jacquard-no-3"},
        "jacquard-no.-14": {"name": "Jacquard No. 14", "quality": "Jacquard", "slug": "jacquard-no-14"},
    }

    def _get_fresh_token(self) -> str:
        """Get a fresh JWT token via email/password login"""
        import os
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
        load_dotenv(env_path, override=True)

        email = os.getenv("SALEOR_EMAIL", "nurullah_cevik1989@hotmail.com")
        password = os.getenv("SALEOR_PASSWORD", "12345678")

        resp = requests.post(self.api_url, json={
            "query": f'mutation {{ tokenCreate(email: "{email}", password: "{password}") {{ token errors {{ field message }} }} }}'
        }, headers={"Content-Type": "application/json"})

        data = resp.json().get("data", {}).get("tokenCreate", {})
        if data.get("token"):
            self.api_token = data["token"]
            return data["token"]
        raise Exception(f"Token refresh failed: {data.get('errors')}")

    def _execute_authed(self, query: str, variables: dict = None) -> dict:
        """Execute with auto token refresh"""
        try:
            return self._execute(query, variables)
        except Exception as e:
            if "Signature verification failed" in str(e) or "expired" in str(e).lower():
                self._get_fresh_token()
                return self._execute(query, variables)
            raise

    def find_or_create_collection(self, folder_name: str) -> str:
        """Find existing collection by slug, or create it. Returns collection ID."""
        info = self.FOLDER_TO_COLLECTION.get(folder_name, {"name": folder_name.replace("-", " ").title(), "quality": ""})
        slug = info.get("slug", folder_name).replace(".", "")

        # Try to find existing
        try:
            existing = self._execute_authed("""
                query ($slug: String!, $channel: String!) {
                    collection(slug: $slug, channel: $channel) { id }
                }
            """, {"slug": slug, "channel": "default-channel"})
            if existing.get("collection"):
                return existing["collection"]["id"]
        except Exception:
            pass

        # Create new collection
        import json
        description = json.dumps({
            "time": 1711400000000,
            "blocks": [{"id": "1", "type": "paragraph", "data": {"text": f"Premium {info['quality']} wool fabric collection. Made-to-measure suits."}}],
            "version": "2.24.3"
        })

        result = self._execute_authed("""
            mutation ($input: CollectionCreateInput!) {
                collectionCreate(input: $input) {
                    collection { id }
                    errors { field message }
                }
            }
        """, {"input": {"name": info["name"], "slug": slug, "description": description}})

        col_data = result.get("collectionCreate", {})
        if col_data.get("errors"):
            raise Exception(f"Collection create failed: {col_data['errors']}")

        collection_id = col_data["collection"]["id"]

        # Publish to all channels
        for ch in self.CHANNELS:
            try:
                self._execute_authed("""
                    mutation ($id: ID!, $input: CollectionChannelListingUpdateInput!) {
                        collectionChannelListingUpdate(id: $id, input: $input) {
                            collection { id }
                            errors { field message }
                        }
                    }
                """, {"id": collection_id, "input": {"addChannels": [{"channelId": ch["id"], "isPublished": True}]}})
            except Exception:
                pass

        return collection_id

    def create_fabric_product(self, fabric_code: str, folder_name: str, color_name: str,
                               image_url: str, suit_style: str = "slim-2pc",
                               extra_images: list = None, fabric_swatch_url: str = None) -> dict:
        """
        Create a complete Saleor product from a fabric code.
        Returns {"product_id": ..., "collection_id": ..., "variant_id": ...}
        """
        import json

        # Step 1: Find or create collection
        collection_id = self.find_or_create_collection(folder_name)
        print(f"  [saleor] Collection: {collection_id}")

        import hashlib, time as _time
        quality = self.FOLDER_TO_COLLECTION.get(folder_name, {}).get("quality", "Premium Wool")
        product_name = f"{fabric_code} - {quality} {color_name} Suit"
        # Add short hash to prevent slug collisions
        slug_base = f"{fabric_code.lower()}-{quality.lower().replace(' ', '-')}-{color_name.lower().replace(' ', '-')}"
        slug_hash = hashlib.md5(str(_time.time()).encode()).hexdigest()[:4]
        product_slug = f"{slug_base}-{slug_hash}"

        description = json.dumps({
            "time": 1711400000000,
            "blocks": [{"id": "1", "type": "paragraph", "data": {
                "text": f"Made-to-measure {color_name} suit in {fabric_code} {quality} wool fabric. Italian tailoring, {suit_style.replace('-', ' ')} fit."
            }}],
            "version": "2.24.3"
        })

        # Step 2: Create product
        result = self._execute_authed("""
            mutation ($input: ProductCreateInput!) {
                productCreate(input: $input) {
                    product { id name slug }
                    errors { field message code }
                }
            }
        """, {"input": {
            "productType": self.PRODUCT_TYPE_SUIT,
            "category": self.CATEGORY_DEFAULT,
            "name": product_name,
            "slug": product_slug,
            "description": description,
            "collections": [collection_id],
        }})

        prod_data = result.get("productCreate", {})
        if prod_data.get("errors"):
            raise Exception(f"Product create failed: {prod_data['errors']}")

        product_id = prod_data["product"]["id"]
        print(f"  [saleor] Product: {product_id} ({product_name})")

        # Step 3: Publish to all channels
        self._execute_authed("""
            mutation ($id: ID!, $input: ProductChannelListingUpdateInput!) {
                productChannelListingUpdate(id: $id, input: $input) {
                    product { id }
                    errors { field message }
                }
            }
        """, {"id": product_id, "input": {
            "updateChannels": [
                {"channelId": ch["id"], "isPublished": True, "visibleInListings": True, "isAvailableForPurchase": True}
                for ch in self.CHANNELS
            ]
        }})

        # Step 4: Create variant
        result = self._execute_authed("""
            mutation ($input: ProductVariantCreateInput!) {
                productVariantCreate(input: $input) {
                    productVariant { id sku }
                    errors { field message }
                }
            }
        """, {"input": {
            "product": product_id,
            "sku": f"{fabric_code}-MTM",
            "name": "Made to Measure",
            "trackInventory": False,
            "attributes": [],
        }})

        var_data = result.get("productVariantCreate", {})
        if var_data.get("errors"):
            print(f"  [saleor] Variant warning: {var_data['errors']}")
            variant_id = None
        else:
            variant_id = var_data["productVariant"]["id"]

            # Step 5: Set prices on all channels
            self._execute_authed("""
                mutation ($id: ID!, $input: [ProductVariantChannelListingAddInput!]!) {
                    productVariantChannelListingUpdate(id: $id, input: $input) {
                        variant { id }
                        errors { field message }
                    }
                }
            """, {"id": variant_id, "input": [
                {"channelId": ch["id"], "price": "599.00"} for ch in self.CHANNELS
            ]})

        # Step 6: Upload product images (lifestyle first, then studio, then fabric swatch)
        self._upload_product_image(product_id, image_url, f"{fabric_code} {color_name} Suit")

        if extra_images:
            for i, img_url in enumerate(extra_images):
                self._upload_product_image(product_id, img_url, f"{fabric_code} {color_name} - View {i+2}")

        if fabric_swatch_url:
            self._upload_product_image(product_id, fabric_swatch_url, f"{fabric_code} - Fabric Swatch")

        total_imgs = 1 + len(extra_images or []) + (1 if fabric_swatch_url else 0)
        print(f"  [saleor] DONE - {total_imgs} images, live on all channels!")
        return {"product_id": product_id, "collection_id": collection_id, "variant_id": variant_id}

    def _upload_product_image(self, product_id: str, image_url: str, alt_text: str):
        """Upload image to product via mediaUrl"""
        try:
            self._execute_authed("""
                mutation ($product: ID!, $mediaUrl: String!, $alt: String) {
                    productMediaCreate(input: {product: $product, mediaUrl: $mediaUrl, alt: $alt}) {
                        media { id }
                        errors { field message }
                    }
                }
            """, {"product": product_id, "mediaUrl": image_url, "alt": alt_text})
        except Exception as e:
            print(f"  [saleor] Image upload warning: {e}")


if __name__ == "__main__":
    # Test connection
    client = SaleorClient()

    print("=" * 60)
    print("Testing Saleor Connection")
    print("=" * 60)

    try:
        collections = client.get_collections()
        print(f"\nFound {len(collections)} collections:\n")

        for col in collections[:10]:  # Show first 10
            print(f"  ID: {col['id']}")
            print(f"  Slug: {col['slug']}")
            print(f"  Name: {col['name']}")
            bg = col.get('backgroundImage')
            print(f"  Background: {bg['url'][:50] + '...' if bg else 'None'}")
            print()

    except Exception as e:
        print(f"Error: {e}")
