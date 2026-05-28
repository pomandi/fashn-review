#!/usr/bin/env python
"""
FASHN Image Generation CLI
Main command-line interface for the FASHN image generation system

IMPORTANT: All generations include saleor_id to enable automatic Saleor update on approval.
"""

import os
import sys
import argparse
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.prompt_manager import PromptManager
from core.generation_tracker import GenerationTracker
from core.image_generator import ImageGenerator
from core.s3_client import S3Client
from core.saleor_client import SaleorClient


# Cache for Saleor collections
_saleor_collections_cache = None


def get_saleor_collections(channel: str = "benelux-b2c", force_refresh: bool = False):
    """
    Fetch collections from Saleor with caching.
    Returns dict: { slug: { id, name, backgroundImage } }
    """
    global _saleor_collections_cache

    if _saleor_collections_cache is not None and not force_refresh:
        return _saleor_collections_cache

    print("  Fetching collections from Saleor...")
    saleor = SaleorClient()

    try:
        collections = saleor.get_collections(channel=channel)
        _saleor_collections_cache = {}

        for col in collections:
            bg_url = col.get('backgroundImage', {}).get('url') if col.get('backgroundImage') else None
            _saleor_collections_cache[col['slug']] = {
                "id": col['id'],  # Saleor GraphQL ID - CRITICAL for updates!
                "name": col['name'],
                "image_url": bg_url,
                "slug": col['slug']
            }

        print(f"  Found {len(_saleor_collections_cache)} collections")
        return _saleor_collections_cache

    except Exception as e:
        print(f"  Warning: Could not fetch from Saleor: {e}")
        print("  Using fallback static collections...")
        return get_fallback_collections()


def get_fallback_collections():
    """Fallback static collections (without Saleor IDs - won't auto-update)"""
    return {
        "tuxedo": {
            "id": None,  # No Saleor ID - manual update required
            "name": "Tuxedo",
            "image_url": "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/WhatsApp_Image_2021-09-04_at_09.17.59_616cab49_thumbnail_4096.jpeg"
        },
        "black-suit": {
            "id": None,
            "name": "Black Suit",
            "image_url": "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/WhatsApp_Image_2021-10-05_at_05.26.54_59449144_thumbnail_4096.jpeg"
        },
        "blue-suit": {
            "id": None,
            "name": "Blue Suit",
            "image_url": "https://saleorme.s3.amazonaws.com/thumbnails/collection-backgrounds/WhatsApp_Image_2021-10-05_at_05.27.25_9dce9985_thumbnail_4096.jpeg"
        },
    }


def print_callback(message):
    """Print callback for progress updates"""
    print(f"  {message}")


def cmd_collections(args):
    """List all collections from Saleor"""
    collections = get_saleor_collections(channel=args.channel, force_refresh=True)

    print("\n" + "=" * 70)
    print(f"SALEOR COLLECTIONS ({args.channel})")
    print("=" * 70)

    for slug, data in sorted(collections.items()):
        saleor_id = data.get('id', 'N/A')
        has_id = "[OK]" if saleor_id else "[--]"
        has_bg = "Yes" if data.get('image_url') else "No"

        print(f"\n{has_id} {slug}")
        print(f"    Name: {data['name']}")
        print(f"    Saleor ID: {saleor_id[:20]}..." if saleor_id and len(saleor_id) > 20 else f"    Saleor ID: {saleor_id}")
        print(f"    Has Background: {has_bg}")

    print(f"\n{'-' * 70}")
    print(f"Total: {len(collections)} collections")
    with_id = len([c for c in collections.values() if c.get('id')])
    print(f"With Saleor ID (can auto-update): {with_id}")


def cmd_generate(args):
    """Generate images for collections"""
    generator = ImageGenerator()
    channel = getattr(args, 'channel', 'benelux-b2c')

    # Fetch collections from Saleor
    collections = get_saleor_collections(channel=channel)

    if args.collection == 'all':
        items = []
        for slug, data in collections.items():
            if not data.get('image_url'):
                print(f"  Skipping {slug}: no background image")
                continue

            items.append({
                "source_type": "collection",
                "source_id": slug,
                "source_name": data["name"],
                "source_image_url": data["image_url"],
                "saleor_id": data.get("id"),  # Include Saleor ID!
                "channel": channel
            })

        if not items:
            print("No collections with background images found!")
            return

        print(f"\nGenerating {len(items)} collection images...")
        results = generator.generate_batch(items, callback=print_callback)

        # Summary
        success = len([r for r in results if r.get('status') == 'pending'])
        failed = len([r for r in results if r.get('status') == 'failed' or 'error' in r])
        print(f"\n{'=' * 50}")
        print(f"GENERATION COMPLETE")
        print(f"{'=' * 50}")
        print(f"  [OK] Generated: {success}")
        print(f"  [FAIL] Failed: {failed}")
        print(f"\nRun 'python cli.py review' to approve/reject images")

    elif args.collection in collections:
        col = collections[args.collection]

        if not col.get('image_url'):
            print(f"Error: Collection '{args.collection}' has no background image to use as source")
            return

        saleor_id = col.get('id')
        if not saleor_id:
            print(f"Warning: No Saleor ID for '{args.collection}' - approved image won't auto-update in Saleor")

        print(f"\nGenerating image for: {col['name']}")
        print(f"  Source: {col['image_url'][:60]}...")
        print(f"  Saleor ID: {saleor_id or 'Not available'}")

        result = generator.generate_single(
            source_type="collection",
            source_id=args.collection,
            source_name=col["name"],
            source_image_url=col["image_url"],
            saleor_id=saleor_id,
            channel=channel,
            callback=print_callback
        )

        print(f"\n{'=' * 50}")
        print(f"Result: {result['status']}")
        if result.get('output', {}).get('s3_url'):
            print(f"S3 URL: {result['output']['s3_url']}")
        if saleor_id:
            print(f"Saleor ID tracked: {saleor_id}")
            print("On approval, this image will auto-update in Saleor!")
        print(f"\nRun 'python cli.py review' to approve/reject")

    else:
        print(f"Unknown collection: {args.collection}")
        print(f"\nAvailable collections:")
        for slug in sorted(collections.keys()):
            print(f"  - {slug}")
        print(f"  - all (generate for all collections)")


def cmd_review(args):
    """Start the review web interface"""
    from app.review_app import app
    print("=" * 60)
    print("FASHN Image Review Interface")
    print("=" * 60)
    print(f"\nStarting at http://localhost:{args.port}")
    print("\nKeyboard shortcuts:")
    print("  Right Arrow or A = Approve")
    print("  Left Arrow or R = Reject")
    print("  Space = Skip to next")
    print("  G = Regenerate")
    print("\nOn approval, images with Saleor ID will auto-update in Saleor!")
    print("=" * 60)
    app.run(debug=True, port=args.port)


def cmd_stats(args):
    """Show statistics"""
    tracker = GenerationTracker()
    prompt_manager = PromptManager()

    gen_stats = tracker.get_statistics()
    prompt_stats = prompt_manager.get_statistics()

    print("\n" + "=" * 50)
    print("GENERATION STATISTICS")
    print("=" * 50)
    print(f"  Total Generations: {gen_stats['total_generations']}")
    print(f"  Approved: {gen_stats['total_approved']}")
    print(f"  Rejected: {gen_stats['total_rejected']}")
    print(f"  Pending Review: {gen_stats['total_pending']}")
    print(f"  Credits Used: {gen_stats['credits_used']}")
    print(f"  Estimated Cost: ${gen_stats['estimated_cost_usd']:.2f}")

    print("\n" + "=" * 50)
    print("PROMPT STATISTICS")
    print("=" * 50)
    print(f"  Active Prompt: {prompt_stats['active_prompt']}")
    print(f"  Total Prompts: {prompt_stats['total_prompts']}")
    print(f"  Overall Approval Rate: {prompt_stats['overall_approval_rate']}%")
    print(f"  Total Learnings: {prompt_stats['total_learnings']}")

    # Show rejection reasons
    reasons = tracker.get_rejection_reasons()
    if reasons:
        print("\n" + "=" * 50)
        print("REJECTION REASONS")
        print("=" * 50)
        for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
            print(f"  {reason}: {count}")


def cmd_prompts(args):
    """List and manage prompts"""
    pm = PromptManager()

    if args.action == 'list':
        prompts = pm.list_prompts()
        print("\n" + "=" * 50)
        print("PROMPTS")
        print("=" * 50)
        for p in prompts:
            status_icon = "✓" if p['status'] == 'active' else "○" if p['status'] == 'testing' else "✗"
            print(f"\n{status_icon} {p['id']} ({p['status']})")
            print(f"  Name: {p['name']}")
            print(f"  Approval Rate: {p['results']['approval_rate']}%")
            print(f"  Generations: {p['results']['total_generations']}")

    elif args.action == 'active':
        active = pm.get_active_prompt()
        print("\n" + "=" * 50)
        print("ACTIVE PROMPT")
        print("=" * 50)
        print(f"ID: {active['id']}")
        print(f"Name: {active['name']}")
        print(f"\nPrompt:\n{active['prompt']}")
        print(f"\nSettings:")
        for k, v in active['settings'].items():
            print(f"  {k}: {v}")

    elif args.action == 'learnings':
        learnings = pm.get_learnings()
        print("\n" + "=" * 50)
        print("LEARNINGS")
        print("=" * 50)
        for l in learnings:
            severity_icon = "🔴" if l['severity'] == 'critical' else "🟡" if l['severity'] == 'high' else "🔵"
            print(f"\n{severity_icon} [{l['date']}] {l['lesson']}")


def cmd_pending(args):
    """List pending generations"""
    tracker = GenerationTracker()
    pending = tracker.get_pending_generations()

    print("\n" + "=" * 70)
    print(f"PENDING REVIEWS ({len(pending)})")
    print("=" * 70)

    for gen in pending:
        saleor_id = gen['source'].get('saleor_id')
        auto_update = "✓ Will auto-update" if saleor_id else "✗ Manual update needed"

        print(f"\n{gen['source']['name']} ({gen['source']['type']})")
        print(f"  Generation ID: {gen['id'][:8]}...")
        print(f"  Saleor ID: {saleor_id[:20]}..." if saleor_id else "  Saleor ID: None")
        print(f"  Auto-update: {auto_update}")
        print(f"  Created: {gen['created_at'][:16]}")
        print(f"  URL: {gen['output'].get('s3_url', 'N/A')}")


def main():
    parser = argparse.ArgumentParser(
        description='FASHN Image Generation System - With Saleor Integration',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py collections            List all collections from Saleor
  python cli.py generate tuxedo        Generate image for tuxedo collection
  python cli.py generate all           Generate images for all collections
  python cli.py review                 Start review web interface
  python cli.py stats                  Show statistics
  python cli.py prompts list           List all prompts
  python cli.py pending                Show pending reviews

Workflow:
  1. python cli.py collections         # See available collections
  2. python cli.py generate tuxedo     # Generate image
  3. python cli.py review              # Approve/reject in browser
  4. Approved images auto-update in Saleor!
        """
    )

    # Global arguments
    parser.add_argument('--channel', default='benelux-b2c', help='Saleor channel (default: benelux-b2c)')

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Collections command (NEW)
    col_parser = subparsers.add_parser('collections', help='List collections from Saleor')
    col_parser.add_argument('--channel', default='benelux-b2c', help='Saleor channel')
    col_parser.set_defaults(func=cmd_collections)

    # Generate command
    gen_parser = subparsers.add_parser('generate', help='Generate images')
    gen_parser.add_argument('collection', help='Collection slug or "all"')
    gen_parser.add_argument('--channel', default='benelux-b2c', help='Saleor channel')
    gen_parser.set_defaults(func=cmd_generate)

    # Review command
    review_parser = subparsers.add_parser('review', help='Start review interface')
    review_parser.add_argument('--port', type=int, default=5000, help='Port number')
    review_parser.set_defaults(func=cmd_review)

    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show statistics')
    stats_parser.set_defaults(func=cmd_stats)

    # Prompts command
    prompts_parser = subparsers.add_parser('prompts', help='Manage prompts')
    prompts_parser.add_argument('action', choices=['list', 'active', 'learnings'])
    prompts_parser.set_defaults(func=cmd_prompts)

    # Pending command
    pending_parser = subparsers.add_parser('pending', help='Show pending reviews')
    pending_parser.set_defaults(func=cmd_pending)

    args = parser.parse_args()

    if args.command:
        args.func(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
