"""
Image Generator - Main generation engine using FASHN API
"""

import os
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from fashn import Fashn

from .prompt_manager import PromptManager
from .generation_tracker import GenerationTracker
from .s3_client import S3Client

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))


class ImageGenerator:
    """Main image generation engine"""

    def __init__(self):
        self.api_key = os.getenv("FASHN_API_KEY")
        self.client = Fashn(api_key=self.api_key)
        self.prompt_manager = PromptManager()
        self.tracker = GenerationTracker()
        self.s3 = S3Client()

        # Multiple base models for variety - randomly selected for each generation
        self.base_models = [
            {
                "name": "chang",
                "url": "https://saleorme.s3.us-east-1.amazonaws.com/fashn-api/base-models/chang.jpeg"
            },
            {
                "name": "drick",
                "url": "https://saleorme.s3.us-east-1.amazonaws.com/fashn-api/base-models/drick.jpeg"
            },
            {
                "name": "dutch-blond",
                "url": "https://saleorme.s3.us-east-1.amazonaws.com/fashn-api/base-models/dutch-blond-model.jpeg"
            },
            {
                "name": "mark",
                "url": "https://saleorme.s3.us-east-1.amazonaws.com/fashn-api/base-models/mark.jpeg"
            }
        ]

    def _get_random_model(self) -> Dict[str, str]:
        """Get a random base model for variety"""
        import random
        return random.choice(self.base_models)

    def generate_single(
        self,
        source_type: str,
        source_id: str,
        source_name: str,
        source_image_url: str,
        saleor_id: str = None,
        channel: str = None,
        prompt_id: Optional[str] = None,
        callback=None
    ) -> Dict[str, Any]:
        """
        Generate a single image

        Args:
            source_type: 'collection' or 'product'
            source_id: Unique identifier (slug or product ID)
            source_name: Human readable name
            source_image_url: URL of source image
            saleor_id: Saleor GraphQL ID (REQUIRED for auto-update on approval)
            channel: Saleor channel slug
            prompt_id: Optional specific prompt to use (defaults to active)
            callback: Optional callback for progress updates

        Returns:
            Generation record with status and URLs

        IMPORTANT: saleor_id must be provided to enable automatic Saleor update on approval.
        Without it, approved images will only be moved to S3 approved folder.
        """
        # Get prompt configuration
        if prompt_id:
            prompt_config = self.prompt_manager.get_prompt_by_id(prompt_id)
        else:
            prompt_config = self.prompt_manager.get_active_prompt()

        if not prompt_config:
            raise ValueError("No prompt configuration found")

        prompt_text = prompt_config['prompt']
        settings = prompt_config['settings']

        # Create generation record
        generation = self.tracker.create_generation(
            source_type=source_type,
            source_id=source_id,
            source_name=source_name,
            source_image_url=source_image_url,
            prompt_id=prompt_config['id'],
            prompt_text=prompt_text,
            settings=settings,
            saleor_id=saleor_id,
            channel=channel
        )

        if callback:
            callback(f"Created generation record: {generation['id']}")

        # Select random model for variety
        selected_model = self._get_random_model()
        if callback:
            callback(f"Selected model: {selected_model['name']}")

        # Build API inputs
        inputs = {
            "product_image": source_image_url,
            "prompt": prompt_text.strip().replace('\n', ' '),
            "aspect_ratio": settings.get('aspect_ratio', '4:5'),
            "resolution": settings.get('resolution', '4k'),
            "num_images": 1,
            "output_format": "png",
        }

        # Add face reference with randomly selected model
        # NOTE: face_reference disabled by default to save credits (was causing high credit usage)
        if settings.get('face_reference', False):
            inputs["face_reference"] = selected_model['url']
            inputs["face_reference_mode"] = settings.get('face_reference_mode', 'match_reference')

        try:
            if callback:
                callback("Sending request to FASHN API...")

            # Call FASHN API
            result = self.client.predictions.subscribe(
                model_name="product-to-model",
                inputs=inputs,
                on_enqueued=lambda pid: callback(f"Queued: {pid}") if callback else None,
                on_queue_update=lambda status: callback(f"Status: {status.status}") if callback else None,
            )

            if result.status == "completed" and result.output:
                fashn_url = result.output[0] if isinstance(result.output, list) else result.output

                if callback:
                    callback(f"Generation complete: {fashn_url}")
                    callback("Uploading to S3...")

                # Upload to S3
                s3_url = self.s3.upload_from_url(
                    image_url=fashn_url,
                    folder="fashn-api/new-collection-images",
                    filename=f"{source_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                )

                # Update generation record with model used
                self.tracker.update_generation_output(
                    generation_id=generation['id'],
                    fashn_url=fashn_url,
                    s3_url=s3_url,
                    status="pending",
                    model_used=selected_model['name']
                )

                if callback:
                    callback(f"Uploaded to S3: {s3_url}")

                return self.tracker.get_generation(generation['id'])

            else:
                # Generation failed
                error_msg = str(getattr(result, 'error', 'Unknown error'))
                self.tracker.update_generation_output(
                    generation_id=generation['id'],
                    fashn_url=None,
                    s3_url=None,
                    status="failed"
                )
                if callback:
                    callback(f"Generation failed: {error_msg}")

                return self.tracker.get_generation(generation['id'])

        except Exception as e:
            if callback:
                callback(f"Error: {str(e)}")
            raise

    def generate_batch(
        self,
        items: List[Dict[str, str]],
        prompt_id: Optional[str] = None,
        delay_between: int = 2,
        callback=None
    ) -> List[Dict[str, Any]]:
        """
        Generate multiple images in batch

        Args:
            items: List of dicts with source_type, source_id, source_name, source_image_url, saleor_id, channel
            prompt_id: Optional specific prompt to use
            delay_between: Seconds to wait between generations
            callback: Optional callback for progress updates

        Returns:
            List of generation records
        """
        results = []
        total = len(items)

        for i, item in enumerate(items):
            if callback:
                callback(f"\n[{i+1}/{total}] Processing: {item['source_name']}")

            try:
                result = self.generate_single(
                    source_type=item['source_type'],
                    source_id=item['source_id'],
                    source_name=item['source_name'],
                    source_image_url=item['source_image_url'],
                    saleor_id=item.get('saleor_id'),
                    channel=item.get('channel'),
                    prompt_id=prompt_id,
                    callback=callback
                )
                results.append(result)
            except Exception as e:
                if callback:
                    callback(f"Error generating {item['source_name']}: {str(e)}")
                results.append({"error": str(e), "source_id": item['source_id']})

            # Delay between requests
            if i < total - 1:
                time.sleep(delay_between)

        return results

    def regenerate(self, generation_id: str, callback=None) -> Dict[str, Any]:
        """
        Regenerate a rejected image

        Args:
            generation_id: ID of the generation to regenerate
            callback: Optional callback for progress updates

        Returns:
            New generation record
        """
        # Mark original for regeneration
        self.tracker.mark_for_regeneration(generation_id)

        # Create new generation record
        new_gen = self.tracker.create_regeneration(generation_id)
        if not new_gen:
            raise ValueError(f"Generation {generation_id} not found")

        # Generate new image
        return self.generate_single(
            source_type=new_gen['source']['type'],
            source_id=new_gen['source']['id'],
            source_name=new_gen['source']['name'],
            source_image_url=new_gen['source']['image_url'],
            prompt_id=new_gen['prompt']['id'],
            callback=callback
        )
