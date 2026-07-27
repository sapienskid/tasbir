/** Single source of truth for API and WebSocket URLs. */
export const API_BASE: string =
  (typeof import.meta !== "undefined" && import.meta.env?.PUBLIC_API_URL) ||
  "http://localhost:8000";

export const WS_URL: string =
  (typeof import.meta !== "undefined" && import.meta.env?.PUBLIC_WS_URL) ||
  API_BASE;
