# API Reference

Local base URL is usually `http://127.0.0.1:8787`.

## Authentication

Protected routes:

- `GET /preview`
- `GET /preview/gallery`
- `GET /preview/screenshot`
- `GET /template/<format>`
- `GET /template-catalog`
- `POST /generate`
- `POST /generate-from-content`

Use either:

- `x-api-key: <one API_KEYS value>`
- `Authorization: Bearer <one API_KEYS value>`

`POST /webhook/ghost` always requires `x-webhook-token` and may also require API auth depending on `security.api_auth.require_for_webhook`.

## `GET /health`

Response:

```json
{
  "ok": true
}
```

## `GET /preview`

Returns the interactive single-template workspace UI.

## `GET /preview/gallery`

Returns the multi-template gallery UI that renders template cards grouped by format.

Useful for design QA when iterating multiple premium templates.

## `GET /preview/screenshot`

Returns a PNG render for a specific preview request.

Required query params:

- `format`
- `templateId` (recommended; defaults to format default template if omitted)

Supports the same content/slot query params as `GET /template/<format>`.

## `GET /template/<format>`

Returns preview HTML for one format.

Formats:

- `instagram-portrait`
- `instagram-square`
- `instagram-story`
- `carousel-post`
- `twitter-card`
- `linkedin-post`

### Query Params

Core:

- `title`
- `caption`
- `imageUrl`
- `brandingColor`
- `brand` or `brandName`
- `templateId`

Carousel:

- `heading`
- `body`
- `slide`
- `total`

Slot values:

- `slot.<key>=...`
- `slot_<key>=...`

Design controls:

- `showBrandBadge`
- `showSlideBadge`
- `showMetaFooter`
- `showTitleKicker`
- `showDecorLayers`
- `textAlign` (`left`, `center`, or `justify`)
- `contentPosition` (`top`, `center`, or `bottom`)
- `imageOpacity` (`0..1`)
- `contentMaxWidth`
- `contentInset`
- `metaLeftText`
- `metaRightText`
- `brandIconUrl`
- `brandIconPosition`

Brand token overrides:

- `tokenPrimaryText`
- `tokenSecondaryText`
- `tokenMutedText`
- `tokenSurfaceBase`
- `tokenSurfaceElevated`
- `tokenBorderSubtle`
- `tokenAccent`
- `tokenAccentForeground`

### Example

```bash
curl "http://127.0.0.1:8787/template/instagram-square?templateId=layout/single-metric-focus&slot.metric_value=9.8K&slot.metric_label=Engagement&slot.headline=Signal%20that%20compounds&slot.insight_line=One%20metric%20needs%20context" \
  -H 'x-api-key: your-api-key'
```

## `GET /template-catalog`

Returns current template registry and format metadata.

### Response Shape

```json
{
  "ok": true,
  "schema_version": 1,
  "catalog_version": "2f9bc4a1",
  "defaults": {
    "carousel_required_slides": 5
  },
  "formats": [
    {
      "id": "instagram-square",
      "width": 1080,
      "height": 1080,
      "caption_source": "instagram_caption",
      "hashtag_count": 3,
      "default_template_id": "layout/editorial-classic"
    }
  ],
  "templates": [
    {
      "id": "layout/editorial-classic",
      "formats": ["instagram-square", "twitter-card", "linkedin-post"],
      "label": "Core Editorial Base",
      "description": "...",
      "file": "templates/editorial-base.html",
      "version": "8a31f10c"
    }
  ],
  "templates_by_format": {
    "instagram-square": ["layout/editorial-classic"]
  }
}
```

## `POST /generate`

Fetches a Ghost post and runs full pipeline.

### Request Body

Required:

- one of `slug` or `url`

Optional:

- `brandingColor`, `brandName`, `prompt`
- `templateIds` (`{ [format]: templateId }`)
- `slotOverrides` (`{ [slotKey]: value }`)
- `brandTokens`
- `design`
- `storage`
- `notifyUrl`
- `llm`
- `image`
- `output`
- `campaign`

### Minimal Example

```json
{
  "slug": "future-of-content-ops"
}
```

### Full Example

```json
{
  "url": "https://blog.example.com/future-of-content-ops/",
  "prompt": "Practical tone for technical founders.",
  "templateIds": {
    "instagram-square": "layout/single-metric-focus",
    "twitter-card": "layout/statement-cta"
  },
  "slotOverrides": {
    "metric_value": "2.4K",
    "metric_label": "Weekly readers"
  },
  "design": {
    "textAlign": "left",
    "imageOpacity": 0.55,
    "formatOverrides": {
      "twitter-card": {
        "contentInset": 40
      }
    }
  },
  "image": {
    "mode": "custom",
    "customUrl": "https://images.example.com/backgrounds/launch.jpg"
  },
  "output": {
    "formats": ["twitter-card", "linkedin-post"],
    "carouselSlides": 4,
    "postCount": 2
  },
  "campaign": {
    "platforms": ["instagram-square", "twitter-card", "linkedin-post"],
    "counts": {
      "instagram-square": 2,
      "twitter-card": 3,
      "linkedin-post": 1
    },
    "strategy": "template-rotation-angle-presets"
  }
}
```

## `POST /generate-from-content`

Runs full pipeline without Ghost fetch.

### Request Body

Required:

- `title`
- one of `content` or `body`

Optional content metadata:

- `excerpt`
- `slug`
- `url`
- `feature_image`
- `tags` (array or comma-separated string)
- `primary_tag`

Supports the same optional overrides as `/generate`.

### Example

```json
{
  "title": "A Better Content Workflow",
  "content": "Start from one source and split into platform-native assets.",
  "prompt": "Clear and no-fluff tone.",
  "output": {
    "formats": ["instagram-square", "linkedin-post"]
  },
  "campaign": {
    "platforms": ["instagram-square", "linkedin-post"],
    "counts": {
      "instagram-square": 2,
      "linkedin-post": 1
    }
  }
}
```

## `POST /webhook/ghost`

Ghost-triggered generation endpoint.

Required header:

- `x-webhook-token: <GHOST_WEBHOOK_TOKEN>`

Slug can be resolved from:

- `payload.post.current.slug`
- `payload.post.slug`
- `payload.slug`
- `payload.post.current.url`
- `payload.url`

## Common Response Fields (`/generate*`)

Top-level response contains:

- `ok`
- `slug`, `post_url`
- `requested_formats`
- `image_source`
- `template_plan`
- `llm_output`
- `campaign_plan` (present when `campaign` is provided)
- `campaign_outputs` (present when `campaign` is provided)
- `assets`
- `variants` (present when `output.postCount > 1`)

`template_plan` includes:

- `required_slot_keys`
- `template_ids`

`assets` includes:

- `instagram_portrait`
- `instagram_square`
- `instagram_story`
- `twitter_card`
- `linkedin_post`
- `carousel` (array)
