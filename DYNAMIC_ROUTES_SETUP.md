# AI Gateway Dynamic Routes Setup Guide

This guide explains how to configure Cloudflare AI Gateway with dynamic routes for the Tasbir application.

## Architecture Overview

Tasbir uses Cloudflare AI Gateway with dynamic routes for LLM operations:

- **No environment variables in code** - All configuration is either hardcoded or stored securely
- **BYOK (Bring Your Own Keys)** - Provider API keys stored in AI Gateway dashboard
- **Single wrangler secret** - Only `AI_GATEWAY_TOKEN` needed for gateway authentication
- **Dynamic routes** - Model selection, fallbacks, and rate limiting configured in dashboard

## Prerequisites

1. Cloudflare account with AI Gateway access
2. AI Gateway: `https://gateway.ai.cloudflare.com/v1/a19f853d1b3f6af9c7f2a8fa1e63bb27/tasbir`
3. Provider API keys (Google AI Studio, etc.)

## Step 1: Configure BYOK (Store Provider Keys)

Store your provider API keys in the AI Gateway dashboard:

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com) → AI → AI Gateway → `tasbir`
2. Navigate to **Provider Keys** section
3. Click **Add API Key**
4. Add your provider keys:
   - **Google AI Studio**: For Gemini models
   - **Workers AI**: No key needed (native)

Example:
- Provider: `Google AI Studio`
- API Key: Your Google AI Studio API key
- Alias: `default`

## Step 2: Enable Gateway Authentication

1. Go to Settings for the `tasbir` gateway
2. Click **Create authentication token**
3. Save the token securely
4. Toggle on **Authenticated Gateway**

## Step 3: Create Dynamic Routes

Navigate to your gateway → **Dynamic Routes** → **Add Route**

### Route 1: `design-tokens`

**Purpose**: Design token generation with fallback

**Flow**:
```
[Start] → [Model: Google AI Studio] → [End]
              ↓ (on error)
         [Model: Workers AI] → [End]
```

**Configuration**:
- Route name: `design-tokens`
- Primary: Google AI Studio (Gemini model)
- Fallback: Workers AI (e.g., `@cf/meta/llama-3.1-8b-instruct`)

### Route 2: `html-layout`

**Purpose**: HTML layout generation

**Flow**: Same as design-tokens

### Route 3: `generic`

**Purpose**: General/fast tasks (classification, etc.)

**Flow**: Same as design-tokens (or simpler single-model)

## Step 4: Set Wrangler Secret

Store the gateway authentication token:

```bash
wrangler secret put AI_GATEWAY_TOKEN --env production
# Paste your gateway auth token when prompted
```

## Step 5: Deploy

```bash
pnpm run deploy
```

## Testing

```bash
curl -X POST https://tasbir.savinpokharel.workers.dev/generate-tokens \
  -H "Content-Type: application/json" \
  -H "x-api-key: <your-app-api-key>" \
  -d '{"vibe": "modern tech startup", "primaryHint": "#3B82F6"}'
```

## Dynamic Route Usage

The application uses these dynamic route names:
- `dynamic/design-tokens` - Design token generation
- `dynamic/html-layout` - HTML layout generation
- `dynamic/generic` - General purpose tasks

## Benefits

1. **Security**: No API keys in code, encrypted storage
2. **Flexibility**: Change models without code changes
3. **Observability**: Full logging and analytics in AI Gateway dashboard
4. **Cost Control**: Rate limiting and budget controls in routes
5. **High Availability**: Automatic fallbacks to Workers AI

## Troubleshooting

### "No such model dynamic/design-tokens"
- Ensure dynamic routes are created and deployed in AI Gateway dashboard
- Verify route names match exactly

### Authentication errors
- Verify `AI_GATEWAY_TOKEN` is set correctly via `wrangler secret`
- Check gateway authentication is enabled in dashboard

### Provider errors
- Verify provider API keys are stored in BYOK section
- Check alias matches (default is `default`)
