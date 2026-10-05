"""Shared request-size limits.

One place for caps that more than one route enforces, so a value can never
drift between endpoints (the compose and task-edit upload caps used to differ).
"""

from __future__ import annotations

# Max characters of a base64-encoded image in a JSON body. base64 inflates by
# ~4/3, so this is effectively a ~7.5 MB image. Matches the default
# ``IMAGE_MAX_BYTES`` (10 MB) for raw downloads.
MAX_UPLOAD_B64 = 10 * 1024 * 1024
