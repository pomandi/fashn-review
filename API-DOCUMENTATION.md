# FASHN AI API Documentation

## Overview

FASHN AI provides fashion-focused generative AI models via REST API. Primary use cases include virtual try-on, AI model generation, and product photography enhancement.

**Dashboard:** https://app.fashn.ai/api
**Documentation:** https://docs.fashn.ai/
**GitHub:** https://github.com/fashn-AI

---

## Authentication

API Key authentication. Set environment variable:

```bash
export FASHN_API_KEY="fa-XXXX..."
# or
export FAL_KEY="fa-XXXX..."
```

---

## Available Endpoints

| Endpoint | Function | Processing Time | Cost |
|----------|----------|-----------------|------|
| Virtual Try-On v1.6 | Realistic garment visualization | 5-17 sec | $0.075/image |
| Product to Model | Flat-lay to on-model conversion | 8-15 sec | $0.075/image |
| Face to Model | Face to fashion model | 10-20 sec | $0.075/image |
| Model Create | Generate AI fashion models | 12-25 sec | $0.075/image |
| Model Variation | Create model variations | 8-15 sec | $0.075/image |
| Model Swap | Replace models, preserve garments | 10-18 sec | $0.075/image |
| Reframe | Adjust composition/aspect ratio | 3-8 sec | $0.075/image |
| Background Change | Replace backgrounds | 5-12 sec | $0.075/image |
| Background Remove | Transparent cutouts | 2-5 sec | $0.075/image |

---

## Virtual Try-On v1.6 (Primary Endpoint)

### Endpoint URL
```
POST https://fal.run/fal-ai/fashn/tryon/v1.6
```

### Parameters

| Parameter | Type | Required | Default | Options |
|-----------|------|----------|---------|---------|
| model_image | string | YES | - | URL or base64 |
| garment_image | string | YES | - | URL or base64 |
| category | enum | NO | auto | tops, bottoms, one-pieces, auto |
| mode | enum | NO | balanced | performance, balanced, quality |
| garment_photo_type | enum | NO | auto | auto, model, flat-lay |
| moderation_level | enum | NO | permissive | none, permissive, conservative |
| num_samples | integer | NO | 1 | 1-4 |
| seed | integer | NO | - | any integer |
| segmentation_free | boolean | NO | true | true/false |
| sync_mode | boolean | NO | false | true/false |
| output_format | enum | NO | png | png, jpeg |

### Response Format

```json
{
  "images": [
    {
      "url": "https://cdn.fashn.ai/xxx/output_0.png"
    }
  ]
}
```

### Output Resolution
- **864 x 1296 pixels** (portrait format)

---

## Code Examples

### Python (requests)

```python
import requests
import os

API_KEY = os.getenv("FASHN_API_KEY")

headers = {
    "Authorization": f"Key {API_KEY}",
    "Content-Type": "application/json"
}

payload = {
    "model_image": "https://example.com/model.jpg",
    "garment_image": "https://example.com/garment.jpg",
    "category": "tops",
    "mode": "quality"
}

response = requests.post(
    "https://fal.run/fal-ai/fashn/tryon/v1.6",
    headers=headers,
    json=payload
)

result = response.json()
print(result["images"][0]["url"])
```

### Python (fal-ai SDK)

```python
import fal_client
import os

# Set API key
fal_client.api_key = os.getenv("FAL_KEY")

# Synchronous call
result = fal_client.subscribe("fal-ai/fashn/tryon/v1.6", arguments={
    "model_image": "https://example.com/model.jpg",
    "garment_image": "https://example.com/garment.jpg",
    "category": "auto",
    "mode": "balanced"
})

print(result["images"][0]["url"])
```

### JavaScript/TypeScript (fal-ai SDK)

```javascript
import { fal } from "@fal-ai/client";

// Configure API key
fal.config({
  credentials: process.env.FAL_KEY
});

// Async call with progress tracking
const result = await fal.subscribe("fal-ai/fashn/tryon/v1.6", {
  input: {
    model_image: "https://example.com/model.jpg",
    garment_image: "https://example.com/garment.jpg",
    category: "auto",
    mode: "balanced"
  },
  logs: true,
  onQueueUpdate: (update) => {
    if (update.status === "IN_PROGRESS") {
      update.logs.map((log) => log.message).forEach(console.log);
    }
  },
});

console.log(result.images[0].url);
```

### cURL

```bash
curl -X POST "https://fal.run/fal-ai/fashn/tryon/v1.6" \
  -H "Authorization: Key $FASHN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model_image": "https://example.com/model.jpg",
    "garment_image": "https://example.com/garment.jpg",
    "category": "auto",
    "mode": "balanced"
  }'
```

---

## Queue Operations (Async Processing)

### Submit Request
```javascript
const { request_id } = await fal.queue.submit("fal-ai/fashn/tryon/v1.6", {
  input: {
    model_image: "...",
    garment_image: "..."
  },
  webhookUrl: "https://your-webhook.com/callback"
});
```

### Check Status
```javascript
const status = await fal.queue.status("fal-ai/fashn/tryon/v1.6", {
  requestId: "764cabcf-b745-4b3e-ae38-1200304cf45b",
  logs: true
});
```

### Fetch Result
```javascript
const result = await fal.queue.result("fal-ai/fashn/tryon/v1.6", {
  requestId: "764cabcf-b745-4b3e-ae38-1200304cf45b"
});
```

---

## File Input Methods

1. **URL:** Public accessible image URL
2. **Base64 Data URI:** `data:image/jpeg;base64,/9j/4AAQ...`
3. **Auto-upload:** Client SDK handles upload automatically

```javascript
// Auto-upload example
const file = new File([buffer], "image.jpg", { type: "image/jpeg" });
const url = await fal.storage.upload(file);
```

---

## Mode Comparison

| Mode | Quality | Speed | Use Case |
|------|---------|-------|----------|
| performance | Good | 5-8 sec | Real-time preview |
| balanced | Better | 8-12 sec | Standard production |
| quality | Best | 12-17 sec | High-quality output |

---

## Category Options

| Category | Description |
|----------|-------------|
| auto | AI automatically detects garment type |
| tops | Shirts, jackets, sweaters, etc. |
| bottoms | Pants, skirts, shorts |
| one-pieces | Dresses, jumpsuits, full outfits |

---

## Pricing

| Plan | Monthly | Credits | Per Image |
|------|---------|---------|-----------|
| On-Demand | - | Pay as you go | $0.075 |
| Tier I | $19 | 282 images | ~$0.067 |
| Tier II | $249 | 4,150 images | ~$0.060 |
| Tier III | $1,249 | 25,594 images | ~$0.049 |

---

## Data Retention

- Generated images are automatically deleted after **72 hours**
- Download or save images immediately after generation
- No long-term storage of user data

---

## Rate Limits & Best Practices

1. Use async queue for batch processing
2. Implement retry logic with exponential backoff
3. Cache results locally when possible
4. Use webhooks for production workflows
5. Compress images before upload for faster processing

---

## Support

- **Email:** support@fashn.ai
- **Discord:** Community support available
- **Status:** Monitor API status at dashboard
