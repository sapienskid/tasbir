import { HttpError } from "./security";

export interface TemplateMetadata {
  id: string;
  name: string;
  description: string;
  slots: string[];
  category: string;
  enabled: boolean;
  createdAt: string;
  updatedAt: string;
}

const SLOT_PATTERN = /\{\{(\w+)\}\}/g;

export function extractSlotsFromHtml(html: string): string[] {
  const slots = new Set<string>();
  let match: RegExpExecArray | null;
  while ((match = SLOT_PATTERN.exec(html)) !== null) {
    slots.add(match[1]);
  }
  return [...slots];
}

export function fillTemplateSlots(html: string, slotValues: Record<string, string>): string {
  let result = html;
  for (const [key, value] of Object.entries(slotValues)) {
    const pattern = new RegExp(`\\{\\{${key}\\}\\}`, "g");
    result = result.replace(pattern, escapeForHtml(value));
  }
  return result;
}

function escapeForHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

export function validateTemplateHtml(html: string): { valid: boolean; errors: string[]; slots: string[] } {
  const errors: string[] = [];
  if (!html.trim()) {
    errors.push("Template HTML cannot be empty");
    return { valid: false, errors, slots: [] };
  }

  const slots = extractSlotsFromHtml(html);

  if (slots.length > 50) {
    errors.push("Too many slots (max 50)");
  }

  return { valid: errors.length === 0, errors, slots };
}

function sanitizeId(id: string): string {
  return id
    .toLowerCase()
    .replace(/[^a-z0-9-_]/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 80);
}

export async function listTemplates(kv: KVNamespace): Promise<TemplateMetadata[]> {
  try {
    const raw = await kv.get("templates:registry", "text");
    if (!raw) return [];
    const parsed = JSON.parse(raw) as TemplateMetadata[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export async function getTemplate(kv: KVNamespace, bucket: R2Bucket, id: string): Promise<{ metadata: TemplateMetadata; html: string } | null> {
  const sanitized = sanitizeId(id);
  const templates = await listTemplates(kv);
  const metadata = templates.find((t) => t.id === sanitized);
  if (!metadata) return null;

  const object = await bucket.get(`templates/${sanitized}.html`);
  if (!object) return null;

  const html = await object.text();
  return { metadata, html };
}

export async function saveTemplate(kv: KVNamespace, bucket: R2Bucket, id: string, html: string, overrides?: { name?: string; description?: string; category?: string }): Promise<TemplateMetadata> {
  const validation = validateTemplateHtml(html);
  if (!validation.valid) {
    throw new HttpError(400, `Template validation failed: ${validation.errors.join("; ")}`);
  }

  const sanitized = sanitizeId(id);
  const templates = await listTemplates(kv);
  const existing = templates.find((t) => t.id === sanitized);
  const now = new Date().toISOString();

  const metadata: TemplateMetadata = {
    id: sanitized,
    name: overrides?.name || existing?.name || sanitized,
    description: overrides?.description || existing?.description || "",
    slots: validation.slots,
    category: overrides?.category || existing?.category || "custom",
    enabled: existing?.enabled ?? true,
    createdAt: existing?.createdAt || now,
    updatedAt: now
  };

  await bucket.put(`templates/${sanitized}.html`, html, {
    httpMetadata: { contentType: "text/html" }
  });

  const updated = existing
    ? templates.map((t) => t.id === sanitized ? metadata : t)
    : [...templates, metadata];

  await kv.put("templates:registry", JSON.stringify(updated));

  return metadata;
}

export async function deleteTemplate(kv: KVNamespace, bucket: R2Bucket, id: string): Promise<boolean> {
  const sanitized = sanitizeId(id);
  const templates = await listTemplates(kv);
  const exists = templates.some((t) => t.id === sanitized);
  if (!exists) return false;

  await bucket.delete(`templates/${sanitized}.html`);

  const updated = templates.filter((t) => t.id !== sanitized);
  await kv.put("templates:registry", JSON.stringify(updated));

  return true;
}

export async function toggleTemplate(kv: KVNamespace, id: string, enabled: boolean): Promise<TemplateMetadata | null> {
  const templates = await listTemplates(kv);
  const sanitized = sanitizeId(id);
  const index = templates.findIndex((t) => t.id === sanitized);
  if (index === -1) return null;

  templates[index] = { ...templates[index], enabled, updatedAt: new Date().toISOString() };
  await kv.put("templates:registry", JSON.stringify(templates));
  return templates[index];
}
