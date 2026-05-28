"""
Generation Tracker - Tracks all image generations, their status, and feedback.

State persistence: local JSON file is the working copy. On startup we hydrate
from R2 if the cloud copy is newer than the in-image seed (so the live state
survives container restarts and redeploys). Every save writes back to R2.
"""

import json
import os
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
import uuid


GENERATIONS_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'generations', 'generations.json')

# R2 key where authoritative state lives. Set R2_STATE_DISABLED=1 to skip cloud sync.
_R2_STATE_KEY = "fashn-review/state/generations.json"
_state_lock = threading.Lock()


def _r2_client_or_none():
    if os.getenv("R2_STATE_DISABLED"):
        return None
    try:
        import boto3
        account_id = os.environ["R2_ACCOUNT_ID"]
        return (boto3.client(
            's3',
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name='auto',
        ), os.getenv("R2_BUCKET_NAME", "pomandi-media"))
    except Exception as e:
        print(f"[tracker] R2 unavailable: {e}")
        return None


def _hydrate_from_r2(local_path: str):
    """R2 is authoritative — if a state file exists there, always use it.
    The local seed is only a bootstrap for the very first deploy when R2 is empty."""
    cli = _r2_client_or_none()
    if cli is None:
        return
    client, bucket = cli
    try:
        obj = client.get_object(Bucket=bucket, Key=_R2_STATE_KEY)
        body = obj["Body"].read()
        json.loads(body)  # validate
    except Exception as e:
        # No remote yet (or fetch failed) — keep the seed.
        print(f"[tracker] R2 state not available, using seed: {e}")
        return

    try:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        tmp = local_path + ".r2-hydrate"
        with open(tmp, "wb") as f:
            f.write(body)
        os.replace(tmp, local_path)
        print(f"[tracker] hydrated {len(body)} bytes from R2 (authoritative)")
    except Exception as e:
        print(f"[tracker] hydrate write failed: {e}")


def _push_to_r2(local_path: str):
    """Push the local JSON state to R2. Best-effort, swallows errors."""
    cli = _r2_client_or_none()
    if cli is None:
        return
    client, bucket = cli
    try:
        with open(local_path, "rb") as f:
            body = f.read()
        client.put_object(
            Bucket=bucket,
            Key=_R2_STATE_KEY,
            Body=body,
            ContentType="application/json",
            CacheControl="no-cache",
        )
    except Exception as e:
        print(f"[tracker] R2 push failed: {e}")


class GenerationStatus(Enum):
    PENDING = "pending"          # Waiting for review
    APPROVED = "approved"        # Approved by user
    REJECTED = "rejected"        # Rejected by user
    REGENERATING = "regenerating"  # Being regenerated
    FAILED = "failed"            # Generation failed


class GenerationTracker:
    def __init__(self):
        self.generations_file = GENERATIONS_FILE
        # Pull authoritative state from R2 (best-effort, before first load).
        with _state_lock:
            _hydrate_from_r2(self.generations_file)
        self.data = self._load_data()

    def _load_data(self) -> dict:
        """Load generations from JSON file"""
        if os.path.exists(self.generations_file):
            with open(self.generations_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "version": "1.0.0",
            "statistics": {
                "total_generations": 0,
                "total_approved": 0,
                "total_rejected": 0,
                "total_pending": 0,
                "credits_used": 0,
                "estimated_cost_usd": 0
            },
            "generations": []
        }

    def _save_data(self):
        """Save generations to JSON file atomically, then push to R2."""
        self.data['last_updated'] = datetime.now().isoformat()
        self._update_statistics()
        with _state_lock:
            tmp = self.generations_file + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.generations_file)
        # Push to R2 in background — never block the request.
        threading.Thread(target=_push_to_r2, args=(self.generations_file,), daemon=True).start()

    def _update_statistics(self):
        """Update statistics based on current generations"""
        gens = self.data['generations']
        self.data['statistics'] = {
            "total_generations": len(gens),
            "total_approved": len([g for g in gens if g['status'] == 'approved']),
            "total_rejected": len([g for g in gens if g['status'] == 'rejected']),
            "total_pending": len([g for g in gens if g['status'] == 'pending']),
            "credits_used": len(gens),
            "estimated_cost_usd": round(len(gens) * 0.075, 2)
        }

    def create_generation(
        self,
        source_type: str,  # 'collection' or 'product'
        source_id: str,    # collection slug or product ID
        source_name: str,
        source_image_url: str,
        prompt_id: str,
        prompt_text: str,
        settings: dict,
        saleor_id: str = None,  # Saleor GraphQL ID (e.g., "Q29sbGVjdGlvbjox")
        channel: str = None     # Channel slug (e.g., "benelux-b2c")
    ) -> Dict[str, Any]:
        """Create a new generation record

        IMPORTANT: saleor_id is the GraphQL ID needed to update the collection/product in Saleor.
        Without this, approved images cannot be automatically applied to the correct entity.
        """
        generation = {
            "id": str(uuid.uuid4()),
            "created_at": datetime.now().isoformat(),
            "status": "generating",
            "source": {
                "type": source_type,
                "id": source_id,
                "name": source_name,
                "image_url": source_image_url,
                "saleor_id": saleor_id,  # GraphQL ID for Saleor mutations
                "channel": channel        # Channel for multi-channel support
            },
            "prompt": {
                "id": prompt_id,
                "text": prompt_text
            },
            "settings": settings,
            "model_used": None,  # Will be updated with the model name used
            "output": {
                "fashn_url": None,
                "s3_url": None
            },
            "feedback": {
                "reviewed_at": None,
                "approved": None,
                "rejection_reason": None,
                "rating": None,
                "notes": None
            },
            "regeneration": {
                "is_regeneration": False,
                "original_generation_id": None,
                "regeneration_count": 0
            }
        }

        self.data['generations'].append(generation)
        self._save_data()
        return generation

    def update_generation_output(
        self,
        generation_id: str,
        fashn_url: str,
        s3_url: str,
        status: str = "pending",
        model_used: str = None
    ):
        """Update generation with output URLs and model used"""
        for gen in self.data['generations']:
            if gen['id'] == generation_id:
                gen['output']['fashn_url'] = fashn_url
                gen['output']['s3_url'] = s3_url
                gen['status'] = status
                gen['completed_at'] = datetime.now().isoformat()
                if model_used:
                    gen['model_used'] = model_used
                self._save_data()
                return gen
        return None

    def approve_generation(
        self,
        generation_id: str,
        rating: int = 5,
        notes: str = None
    ):
        """Approve a generation"""
        self.reload()
        for gen in self.data['generations']:
            if gen['id'] == generation_id:
                gen['status'] = 'approved'
                gen['feedback']['reviewed_at'] = datetime.now().isoformat()
                gen['feedback']['approved'] = True
                gen['feedback']['rating'] = rating
                gen['feedback']['notes'] = notes
                self._save_data()
                return gen
        return None

    def reject_generation(
        self,
        generation_id: str,
        reason: str,
        notes: str = None
    ):
        """Reject a generation with reason"""
        self.reload()
        for gen in self.data['generations']:
            if gen['id'] == generation_id:
                gen['status'] = 'rejected'
                gen['feedback']['reviewed_at'] = datetime.now().isoformat()
                gen['feedback']['approved'] = False
                gen['feedback']['rejection_reason'] = reason
                gen['feedback']['notes'] = notes
                self._save_data()
                return gen
        return None

    def mark_for_regeneration(self, generation_id: str) -> Dict[str, Any]:
        """Mark a rejected generation for regeneration"""
        for gen in self.data['generations']:
            if gen['id'] == generation_id:
                gen['status'] = 'regenerating'
                self._save_data()
                return gen
        return None

    def create_regeneration(self, original_generation_id: str) -> Optional[Dict[str, Any]]:
        """Create a new generation based on a rejected one"""
        original = self.get_generation(original_generation_id)
        if not original:
            return None

        new_gen = self.create_generation(
            source_type=original['source']['type'],
            source_id=original['source']['id'],
            source_name=original['source']['name'],
            source_image_url=original['source']['image_url'],
            prompt_id=original['prompt']['id'],
            prompt_text=original['prompt']['text'],
            settings=original['settings']
        )

        # Mark as regeneration
        new_gen['regeneration']['is_regeneration'] = True
        new_gen['regeneration']['original_generation_id'] = original_generation_id
        new_gen['regeneration']['regeneration_count'] = original['regeneration']['regeneration_count'] + 1

        self._save_data()
        return new_gen

    def reload(self):
        """Reload data from disk (picks up changes from other processes)"""
        self.data = self._load_data()

    def get_generation(self, generation_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific generation by ID"""
        self.reload()
        for gen in self.data['generations']:
            if gen['id'] == generation_id:
                return gen
        return None

    def get_pending_generations(self) -> List[Dict[str, Any]]:
        """Get all generations pending review"""
        self.reload()
        return [g for g in self.data['generations'] if g['status'] == 'pending']

    def get_generations_by_source(self, source_id: str) -> List[Dict[str, Any]]:
        """Get all generations for a specific source (collection/product)"""
        return [g for g in self.data['generations'] if g['source']['id'] == source_id]

    def get_statistics(self) -> dict:
        """Get generation statistics"""
        return self.data['statistics']

    def get_rejection_reasons(self) -> Dict[str, int]:
        """Get counts of rejection reasons"""
        reasons = {}
        for gen in self.data['generations']:
            if gen['status'] == 'rejected':
                reason = gen['feedback'].get('rejection_reason', 'Unknown')
                reasons[reason] = reasons.get(reason, 0) + 1
        return reasons


if __name__ == "__main__":
    # Test
    tracker = GenerationTracker()

    print("Statistics:")
    stats = tracker.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print(f"\nPending Reviews: {len(tracker.get_pending_generations())}")
