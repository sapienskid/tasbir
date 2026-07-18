import { api } from "./client";

export interface Template {
  id: string;
  name: string;
  description: string;
  html: string;
  slots: Record<string, string>;
  enabled: boolean;
}

export interface TemplateCreate {
  name: string;
  description?: string;
  html: string;
  slots?: Record<string, string>;
  enabled?: boolean;
}

export interface TemplateUpdate {
  name?: string;
  description?: string;
  html?: string;
  slots?: Record<string, string>;
  enabled?: boolean;
}

export async function listTemplates(
  enabledOnly = true
): Promise<Template[]> {
  return api.get(`/templates?enabled_only=${enabledOnly}`);
}

export async function getTemplate(id: string): Promise<Template> {
  return api.get(`/templates/${id}`);
}

export async function createTemplate(
  data: TemplateCreate
): Promise<Template> {
  return api.post("/templates", data);
}

export async function updateTemplate(
  id: string,
  data: TemplateUpdate
): Promise<Template> {
  return api.put(`/templates/${id}`, data);
}

export async function deleteTemplate(id: string): Promise<void> {
  return api.delete(`/templates/${id}`);
}
