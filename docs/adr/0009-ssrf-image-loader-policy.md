# ADR-0009 — SSRF Guard on the Image Loader

- Status: accepted
- Date: 2026-08-01
- Related: ADR-0008 (trust boundary)

## Context

`prepare_images()` fetched any URL the API caller supplied (`images[].url`)
with `follow_redirects=True` and no limits. A compromised or malicious caller
could use the worker as a proxy to scan the docker network (redis, the API,
the render service) or cloud metadata (`169.254.169.254`), or pull
unbounded payloads into memory.

## Decision

The worker validates every image URL before fetching:

- **Scheme**: `http`/`https` only.
- **Blocked ranges** (never legitimate for image loading): loopback, link-local
  (incl. cloud metadata), multicast, broadcast, CGNAT, benchmarking/TEST-NET,
  IANA special-purpose, documentation, and their IPv6 equivalents.
- **LAN is trusted by default**: RFC1918 (`10/8`, `172.16/12`, `192.168/16`)
  and IPv6 ULA are allowed — this is a local-only deployment and n8n on the
  same network must keep working.
- **DNS resolution** is checked at fetch time; a hostname resolving to a
  blocked address is rejected. `IMAGE_ALLOW_HOSTS` is an explicit opt-in for
  trusted internal hosts that must bypass the block.
- **Size cap** (`IMAGE_MAX_BYTES`, default 10 MB), **redirect cap** (2), and
  an image content-type check.

## Consequences

- The worker can no longer be pointed at loopback/metadata/link-local hosts,
  closing the primary SSRF vector.
- LAN image hosts (e.g. n8n serving images) keep working because RFC1918 is
  allowed by default.
- The remaining DNS-rebinding window is accepted for a LAN-only deployment;
  a truly hostile network would move the renderer off-network and pin IPs.
