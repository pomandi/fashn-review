# FASHN Image Generation System

Professional AI-powered image generation system for e-commerce product photography using FASHN API.

## 🎯 Overview

This system automates the generation of high-quality product/collection images using FASHN's Product-to-Model API. It includes:

- **Prompt Management** - Version-controlled prompts with performance tracking
- **Batch Generation** - Generate images for multiple products/collections
- **Review Interface** - Web-based approval system with swipe gestures
- **Learning System** - Tracks what works and what doesn't
- **S3 Integration** - Automatic upload and organization

## 📁 Folder Structure

```
fashn-api/
├── app/                          # Web application
│   ├── review_app.py            # Flask review server
│   ├── templates/               # HTML templates
│   │   └── review.html          # Swipe review interface
│   └── static/                  # Static assets
├── core/                        # Core modules
│   ├── __init__.py
│   ├── prompt_manager.py        # Prompt versioning & tracking
│   ├── generation_tracker.py    # Generation history & feedback
│   ├── image_generator.py       # FASHN API integration
│   └── s3_client.py             # S3 operations
├── data/                        # Data storage (JSON)
│   ├── prompts/
│   │   └── prompts.json         # Prompt versions & learnings
│   ├── generations/
│   │   └── generations.json     # Generation history
│   └── feedback/                # Feedback data
├── output/                      # Local output
│   ├── approved/                # Approved images
│   └── rejected/                # Rejected images
├── logs/                        # Log files
├── cli.py                       # Command-line interface
├── .env                         # API keys (not in git)
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd fashn-api
pip install -r requirements.txt
```

### 2. Configure API Key

Create `.env` file:
```env
FASHN_API_KEY=fa-XXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

### 3. Generate Images

```bash
# Generate single collection
python cli.py generate tuxedo

# Generate all collections
python cli.py generate all
```

### 4. Review Images

```bash
# Start review interface
python cli.py review

# Open http://localhost:5000 in browser
```

## 💻 CLI Commands

```bash
# Generate images
python cli.py generate <collection>   # Single collection
python cli.py generate all            # All collections

# Review interface
python cli.py review                  # Start web UI (port 5000)
python cli.py review --port 8080      # Custom port

# Statistics
python cli.py stats                   # Show all statistics

# Prompts
python cli.py prompts list            # List all prompts
python cli.py prompts active          # Show active prompt
python cli.py prompts learnings       # Show learnings

# Pending reviews
python cli.py pending                 # List pending generations
```

## 🖥️ Review Interface

The web-based review interface supports:

### Keyboard Shortcuts
| Key | Action |
|-----|--------|
| `→` or `A` | Approve |
| `←` or `R` | Reject |
| `Space` | Skip |
| `G` | Regenerate |
| `Esc` | Close modal |

### Touch/Swipe
- **Swipe Right** → Approve
- **Swipe Left** → Reject

### Rejection Reasons
When rejecting, select a reason for tracking:
- Quality not acceptable
- Wrong pose/angle
- Garment not visible properly
- Background issues
- Face/model issues
- Custom reason

## 📊 Prompt Management

### Current Active Prompt (v3_production)

```
Tall elegant blond Dutch man, age 28-32, refined Italian style tailoring,
standing confidently with full body visible. Sharp symmetrical features,
clean-shaven, healthy glowing skin. Relaxed yet confident pose.
Soft out-of-focus Italian city street background inspired by Milan fashion district,
warm natural daylight, gentle shadows. Studio-quality lighting, perfect exposure,
professional fashion editorial photography, high-end catalog quality.
```

### Settings
| Parameter | Value | Description |
|-----------|-------|-------------|
| `aspect_ratio` | `4:5` | Optimal for mobile, Meta Ads, website |
| `resolution` | `4k` | Ultra high definition |
| `face_reference` | `true` | Use base model for consistency |
| `face_reference_mode` | `match_reference` | Match face identity |

### Prompt Versioning

Prompts are versioned and tracked:
- **v1_initial** - Deprecated (Vogue watermark issue)
- **v2_no_brand** - Deprecated (bad camera angle with 9:16)
- **v3_production** - Active ✓

## 📚 Learnings

Critical learnings captured from experience:

| Severity | Learning |
|----------|----------|
| 🔴 CRITICAL | Never use brand names (Vogue, GQ) - they appear as watermarks |
| 🔴 CRITICAL | Use 'product-to-model' endpoint, NOT 'tryon' |
| 🟡 HIGH | 9:16 aspect ratio causes overhead camera angles |
| 🔵 INFO | 4:5 aspect ratio is optimal for mobile-first |

## 💰 Pricing

| Item | Cost |
|------|------|
| Per image | ~$0.075 |
| 100 images | ~$7.50 |
| 1000 images | ~$75.00 |

## 🔄 Workflow

```
┌─────────────────┐
│  Source Image   │ (Collection/Product photo)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  FASHN API      │ (Product-to-Model)
│  + Prompt       │
│  + Settings     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Generated      │ → S3 Upload
│  Image          │   (new-collection-images/)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Review UI      │ ← Human Review
│  (Swipe)        │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐ ┌───────┐
│Approve│ │Reject │
└───┬───┘ └───┬───┘
    │         │
    ▼         ▼
┌───────┐ ┌───────────┐
│S3:    │ │Regenerate │
│approved│ │or Archive │
└───────┘ └───────────┘
         │
         ▼
┌─────────────────┐
│  Learnings      │ (Update prompts)
│  Captured       │
└─────────────────┘
```

## 🗄️ S3 Structure

```
saleorme/
└── fashn-api/
    ├── base-models/
    │   └── dutch-blond-model.jpeg     # Face reference
    ├── new-collection-images/         # Pending review
    │   ├── tuxedo_20251211_071729.png
    │   └── ...
    ├── approved/                       # Production ready
    │   └── ...
    └── rejected/                       # Archived
        └── ...
```

## 🔧 API Configuration

### FASHN API
- **Endpoint**: `product-to-model`
- **Base URL**: Via FASHN Python SDK
- **Authentication**: API Key

### AWS S3
- **Bucket**: `saleorme`
- **Region**: `us-east-1`

## 📈 Statistics Tracking

The system tracks:
- Total generations
- Approval/rejection rates
- Cost estimation
- Rejection reasons
- Prompt performance
- Learnings from failures

View stats anytime:
```bash
python cli.py stats
```

## 🚨 Troubleshooting

### "Authentication Error"
- Check `FASHN_API_KEY` in `.env`
- Verify API key is valid at https://app.fashn.ai/api

### "S3 Upload Failed"
- Check AWS credentials in `core/s3_client.py`
- Verify bucket permissions

### "Generation Failed"
- Check source image quality
- Ensure image URL is accessible
- Review FASHN API logs

### "Bad Camera Angle"
- Don't use 9:16 aspect ratio
- Stick to 4:5 or 3:4

### "Watermark on Image"
- Remove brand names from prompt
- Avoid: Vogue, GQ, etc.

## 🔜 Future Improvements

- [ ] Product image batch import from Saleor
- [ ] Automatic Saleor collection update
- [ ] Slack notifications for review
- [ ] A/B testing for prompts
- [ ] Cost budgeting alerts
- [ ] Scheduled batch generation

## 📞 Support

- **FASHN Docs**: https://docs.fashn.ai/
- **FASHN Dashboard**: https://app.fashn.ai/api
