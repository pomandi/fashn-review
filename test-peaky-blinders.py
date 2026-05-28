#!/usr/bin/env python
"""
Test script - Peaky Blinders style transformation attempt using FASHN API
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.s3_client import S3Client
from fashn import Fashn

load_dotenv()

def main():
    # Local image path
    local_image = r"c:\Users\nurul\Downloads\Adsız tasarım\25.png"

    if not os.path.exists(local_image):
        print(f"ERROR: Image not found: {local_image}")
        return

    print("=" * 60)
    print("PEAKY BLINDERS STYLE TEST")
    print("=" * 60)

    # Step 1: Upload to S3
    print("\n[1/3] Uploading image to S3...")
    s3 = S3Client()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    s3_url = s3.upload_file(
        local_path=local_image,
        folder="fashn-api/test-inputs",
        filename=f"peaky_source_{timestamp}.png"
    )

    if not s3_url:
        print("ERROR: Failed to upload to S3")
        return

    print(f"   Uploaded: {s3_url}")

    # Step 2: Call FASHN API with Peaky Blinders prompt
    print("\n[2/3] Calling FASHN API with Peaky Blinders style prompt...")

    api_key = os.getenv("FASHN_API_KEY")
    if not api_key:
        print("ERROR: FASHN_API_KEY not found in .env")
        return

    client = Fashn(api_key=api_key)

    # Peaky Blinders style prompt
    peaky_prompt = """
    Tall elegant man in 1920s Peaky Blinders style, Birmingham gangster aesthetic.
    Wearing a classic flat cap (newsboy cap), vintage three-piece tweed suit with
    herringbone pattern. Pocket watch chain visible. Standing confidently with
    dramatic moody lighting. Dark atmospheric background with industrial Birmingham
    vibes. Sepia-toned vintage photography style. Post-WWI era fashion.
    Sharp shadows, dramatic noir lighting. Professional cinematic photography.
    """

    inputs = {
        "product_image": s3_url,
        "prompt": peaky_prompt.strip().replace('\n', ' '),
        "aspect_ratio": "4:5",
        "resolution": "4k",
        "num_images": 1,
        "output_format": "png",
    }

    print(f"   Sending to FASHN API...")
    print(f"   Prompt: {peaky_prompt[:100]}...")

    try:
        result = client.predictions.subscribe(
            model_name="product-to-model",
            inputs=inputs,
            on_enqueued=lambda pid: print(f"   Queued: {pid}"),
            on_queue_update=lambda status: print(f"   Status: {status.status}"),
        )

        if result.status == "completed" and result.output:
            fashn_url = result.output[0] if isinstance(result.output, list) else result.output
            print(f"\n[3/3] SUCCESS! Generated image:")
            print(f"   FASHN URL: {fashn_url}")

            # Upload result to S3
            print("\n   Uploading result to S3...")
            result_url = s3.upload_from_url(
                image_url=fashn_url,
                folder="fashn-api/peaky-blinders-output",
                filename=f"peaky_result_{timestamp}.png"
            )

            if result_url:
                print(f"   S3 Result: {result_url}")

            print("\n" + "=" * 60)
            print("DONE!")
            print("=" * 60)

        else:
            print(f"\n[3/3] FAILED!")
            print(f"   Status: {result.status}")
            print(f"   Error: {getattr(result, 'error', 'Unknown')}")

    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
