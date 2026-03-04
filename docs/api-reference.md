# API Reference

Base URL in local dev is usually `http://127.0.0.1:8787`.

## Authentication

Protected routes:

- `GET /template/<format>`
- `GET /template-catalog`
- `POST /generate`
- `POST /generate-from-content`

Provide one of:

- `x-api-key: <one of API_KEYS>`
- `Authorization: Bearer <one of API_KEYS>`

## `GET /health`

Simple health endpoint.

Response:

```json
{
  "ok": true
}
```

## `GET /template/<format>`

Renders preview HTML for one format without uploading to R2.

Supported formats:

- `instagram-post`
- `instagram-story`
- `carousel-slide`
- `twitter-card`
- `linkedin-post`

This route can be disabled with `features.enable_template_preview = false`.

### Query Parameters

Core:

- `title`
- `caption`
- `imageUrl`
- `brandingColor`
- `brand` or `brandName`
- `templateStyle`
- `templateId`
- `templateArchetype` (or `archetype`)
- `fontProfile`

Carousel-only:

- `heading`
- `body`
- `slide`
- `total`

Slot values:

- `slot.<key>=...`
- `slot_<key>=...`

Design controls:

- `preset`
- `showBrandBadge`
- `showSlideBadge`
- `showMetaFooter`
- `showTitleKicker`
- `textAlign`
- `imageOpacity`
- `contentMaxWidth`
- `contentInset`
- `metaLeftText`
- `metaRightText`

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
curl "http://127.0.0.1:8787/template/twitter-card?templateStyle=bold&templateArchetype=promo&fontProfile=bold-campaign&slot.headline=Launch%20Week&slot.supporting_line=Read%20the%20full%20guide&slot.cta_text=Read%20now" \
  -H 'x-api-key: your-api-key'
```

Response content type: `text/html`.

## `GET /template-catalog`

Returns a testing catalog of styles, formats, archetypes, fonts, templates, and template versions.

Useful for:

- validating available `templateStyle` / `postArchetype` combinations
- verifying template IDs per format
- tracking template changes via `catalog_version` and per-template `version`

### Example

```bash
curl "http://127.0.0.1:8787/template-catalog" \
  -H 'x-api-key: your-api-key'
```

### Response (shape)

```json
{
  "ok": true,
  "schema_version": 1,
  "catalog_version": "2f9bc4a1",
  "defaults": {
    "template_style": "editorial",
    "post_archetype": "insight",
    "font_profile": "editorial-serif",
    "carousel_required_slides": 5
  },
  "styles": [{ "id": "editorial", "label": "Editorial" }],
  "archetypes": [{ "id": "insight", "label": "Insight" }],
  "font_profiles": [{ "id": "editorial-serif", "label": "Editorial Serif" }],
  "formats": [{ "id": "instagram-post", "default_template_id": "instagram-post/editorial" }],
  "templates": [{ "id": "instagram-post/editorial", "version": "8a31f10c" }],
  "templates_by_format": { "instagram-post": ["instagram-post/editorial"] },
  "styles_by_format": { "instagram-post": ["editorial", "data"] }
}
```

## `POST /generate`

Fetches a Ghost post and runs full pipeline.

### Request Body

Required (one of):

- `slug`
- `url` (slug is parsed from URL)

Optional overrides:

- `brandingColor`
- `brandName`
- `templateStyle`
- `postArchetype`
- `fontProfile`
- `templateIds`
- `slotOverrides`
- `brandTokens`
- `design`
- `storage`
- `notifyUrl`
- `llm`
- `image`
- `output`

### Example

```json
{
  "slug": "future-of-content-ops",
  "templateStyle": "data",
  "postArchetype": "metric",
  "fontProfile": "data-mono",
  "templateIds": {
    "instagram-post": "instagram-post/stat-split",
    "twitter-card": "twitter-card/data-strip"
  },
  "slotOverrides": {
    "metric_value": "2.4K",
    "metric_label": "Weekly readers",
    "headline": "Signal that compounds"
  },
  "llm": {
    "userInstructionsAppend": "Prefer practical tone and avoid buzzwords.",
    "temperature": 0.1
  },
  "image": {
    "mode": "custom",
    "customUrl": "https://images.example.com/backgrounds/launch.jpg"
  },
  "output": {
    "formats": ["twitter-card", "linkedin-post"],
    "carouselSlides": 3
  },
  "storage": {
    "mode": "versioned",
    "includeDate": true,
    "runId": "launch-a"
  }
}
```

## `POST /generate-from-content`

Runs full pipeline without Ghost fetch.

### Request Body

Required:

- `title`
- `content` (or `body`)

Optional source fields:

- `excerpt`
- `slug`
- `url`
- `feature_image`
- `tags` (array or comma-separated string)
- `primary_tag`

Optional design/storage fields are the same as `/generate`.

### Example

```json
{
  "title": "A Better Content Workflow",
  "content": "Start from one source and split into platform-native assets.",
  "templateStyle": "editorial",
  "postArchetype": "insight",
  "slotOverrides": {
    "headline": "Ship with less friction",
    "supporting_line": "One source post, many quality outputs"
  }
}
```

## `POST /webhook/ghost`

Webhook trigger endpoint for Ghost events.

`GHOST_WEBHOOK_TOKEN` is required. Send header:

- `x-webhook-token: <token>`

Slug can be extracted from:

- `payload.post.current.slug`
- `payload.post.slug`
- `payload.slug`
- URL forms (`payload.post.current.url`, `payload.url`)

## Successful Response Shape

`/generate`, `/generate-from-content`, `/webhook/ghost` return:

```json
{
  "ok": true,
  "slug": "example-post",
  "post_url": "https://example.com/example-post/",
  "requested_formats": ["twitter-card", "linkedin-post"],
  "image_source": {
    "source": "custom",
    "imageUrl": "https://..."
  },
  "llm_output": {
    "instagram_caption": "...",
    "twitter_caption": "...",
    "linkedin_caption": "...",
    "carousel_slides": [{ "heading": "...", "body": "..." }],
    "hashtags": ["#..."],
    "image_prompt": "...",
    "use_feature_image": true,
    "template_style": "editorial",
    "post_archetype": "insight",
    "font_profile": "editorial-serif",
    "slot_content": {
      "headline": "..."
    }
  },
  "assets": {
    "instagram_post": null,
    "instagram_story": null,
    "twitter_card": { "format": "twitter-card", "key": "...", "url": null },
    "linkedin_post": { "format": "linkedin-post", "key": "...", "url": null },
    "carousel": []
  }
}
```

`image.mode` supports:

- `auto` (default chain)
- `feature`
- `stock`
- `ai`
- `custom` (requires `image.customUrl`)

`output.formats` supports:

- `instagram-post`
- `instagram-story`
- `carousel-slide`
- `twitter-card`
- `linkedin-post`

## Error Responses

Typical errors:

- `400` invalid JSON, missing required fields
- `401` invalid API key or invalid webhook token
- `413` request body too large
- `415` unsupported content-type
- `429` rate limit exceeded
- `403` template preview disabled
- `404` route not found or Ghost slug missing
- `500` missing env vars or unexpected runtime errors

Error shape:

```json
{
  "error": "message"
}
```
