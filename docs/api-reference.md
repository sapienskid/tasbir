# API Reference

Local base URL is usually `http://127.0.0.1:8787`.

## Authentication

Protected routes:

- `GET /template/<format>`
- `GET /preview/screenshot`
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

### Example

```bash
curl "http://127.0.0.1:8787/template/instagram-square?templateId=layout/single-metric-focus&slot.metric_value=9.8K&slot.metric_label=Engagement&slot.headline=Signal%20that%20compounds&slot.insight_line=One%20metric%20needs%20context" \
  -H 'x-api-key: your-api-key'
```

## `POST /generate`

Fetches a Ghost post and runs full pipeline.

### Request Body

Required:

- one of `slug` or `url`

Optional:

- `brandName`, `prompt`
- `templateIds` (`{ [format]: templateId }`)
- `slotOverrides` (`{ [slotKey]: value }`)
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

`llm_output` includes:

- `instagram_caption`
- `twitter_caption`
- `linkedin_caption`
- `carousel_slides` (`[{ heading, body }]`)
- `hashtags`
- `image_prompt`
- `stock_search_query`
- `use_feature_image`
- `slot_content`

`assets` includes:

- `instagram_portrait`
- `instagram_square`
- `instagram_story`
- `twitter_card`
- `linkedin_post`
- `carousel` (array)

## LLM Overrides (`llm`)

Optional field accepted by both generation endpoints:

- `systemPrompt` (`string` or `string[]`)
- `userInstructions` (`string` or `string[]`)
- `userInstructionsAppend` (`string`)
- `temperature` (`number`, clamped to `0..2`)
- `maxTokens` (`number`, clamped to `256..4096`)

## Image Options (`image`)

Optional field accepted by both generation endpoints:

- `mode`: `auto | none | feature | ai | custom`
- `customUrl`: required when `mode=custom`
- `prompt`: optional prompt override used for AI image mode
- `allowAi`: optional boolean override
- `preferFeature`: optional boolean override

## Proposed Agentic Contract (Design Only)

This contract is planned and not currently implemented.

Goal: use an orchestrator agent to plan and generate multi-platform campaigns from source content.

Recommended request additions:

- `agent.mode`: `orchestrated`
- `agent.promptProfile`: central prompt profile key (for behavior customization)
- `agent.platformGoals.instagram`: feed/carousel/story counts
- `agent.platformGoals.facebook`: reuse/mutate Instagram plan
- `agent.platformGoals.linkedin`: post count and tone controls
- `agent.platformGoals.twitter`: post count and brevity controls
- `agent.renderPolicy.allowMarkdown`: boolean
- `agent.renderPolicy.allowMath`: boolean
- `agent.renderPolicy.allowDiagrams`: boolean
- `agent.renderPolicy.allowTextInAiImages`: default `false`

Recommended response additions:

- `campaign_plan.platform_posts[]` with platform, post_type, angle, template_id
- `creative_decisions[]` with rationale for template and format choices
- `render_checks[]` with overflow/fit/markup validation status
- `prompt_trace` (optional) with prompt profile/version IDs used by each agent role

Recommended error behavior:

- `422` when required template slot keys are missing after retries/fallback
- `422` when render fit checks fail and no valid fallback template is found
