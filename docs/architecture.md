# Architecture Flow

```mermaid
flowchart TD
    A[Author YAML + HTML templates] --> B[Build: pnpm run build:assets]
    B --> C[Generate src/generated/template-assets.ts]
    C --> D[Worker runtime]

    D --> E{Input trigger}
    E -->|POST /generate| F[Fetch Ghost post]
    E -->|POST /generate-from-content| G[Build in-memory post]
    E -->|POST /webhook/ghost| F

    F --> H[Workers AI generation]
    G --> H

    H --> H1[Returns: captions, hashtags, slides,
image_prompt, template_style,
post_archetype, font_profile, slot_content]

    H1 --> I[Select image source]
    H1 --> J[Resolve template per format
(templateId override -> style+archetype -> fallbacks)]
    H1 --> J2[Resolve font profile
(request override -> model font_profile -> config mappings)]
    H1 --> K[Merge slot values
(model slot_content + request slotOverrides + slot defaults)]

    I --> L[Render HTML templates via Browser Rendering]
    J --> L
    J2 --> L
    K --> L

    L --> M[Upload PNG assets to R2]
    M --> N[Return JSON response]
    N --> O[Optional notify webhook]
```

## Runtime routes

- `POST /generate`
- `POST /generate-from-content`
- `POST /webhook/ghost`
- `GET /template/<format>` (if enabled)

## Output formats

Configured in YAML `formats`:
- `instagram-post`
- `instagram-story`
- `carousel-slide`
- `twitter-card`
- `linkedin-post`
