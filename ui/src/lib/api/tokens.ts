import { api } from "./client";

export interface DesignToken {
  id: string;
  name: string;
  data: Record<string, unknown>;
  version: number;
  source: string;
}

export interface TokenCreate {
  name: string;
  data: Record<string, unknown>;
  source?: string;
}

export async function listTokens(): Promise<DesignToken[]> {
  return api.get("/tokens");
}

export async function getToken(id: string): Promise<DesignToken> {
  return api.get(`/tokens/${id}`);
}

export async function createToken(
  data: TokenCreate
): Promise<DesignToken> {
  return api.post("/tokens", data);
}

export async function updateToken(
  id: string,
  data: { data: Record<string, unknown> }
): Promise<DesignToken> {
  return api.put(`/tokens/${id}`, data);
}

export async function deleteToken(id: string): Promise<void> {
  return api.delete(`/tokens/${id}`);
}

export async function generateTokens(
  brandName: string
): Promise<DesignToken> {
  return api.post(`/tokens/generate?brand_name=${brandName}`);
}
