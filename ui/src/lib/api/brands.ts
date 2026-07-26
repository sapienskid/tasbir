import { api } from "./client";

export interface Brand {
  id: string;
  name: string;
  description: string;
  data: {
    tone?: string;
    primary_color?: string;
    secondary_color?: string;
    logo_url?: string;
    style_notes?: string;
    tokens?: Record<string, unknown>;
    [key: string]: unknown;
  };
  version: number;
  source: string;
}

export async function listBrands(): Promise<Brand[]> {
  return api.get("/brands");
}

export async function getBrand(id: string): Promise<Brand> {
  return api.get(`/brands/${id}`);
}

export async function createBrand(data: {
  name: string;
  description: string;
  logo_url?: string;
  tone?: string;
  primary_color?: string;
  secondary_color?: string;
}): Promise<Brand> {
  return api.post("/brands", data);
}

export async function updateBrand(
  id: string,
  data: {
    name?: string;
    description?: string;
    logo_url?: string;
    tone?: string;
    primary_color?: string;
    secondary_color?: string;
    tokens?: Record<string, unknown>;
  }
): Promise<Brand> {
  return api.put(`/brands/${id}`, data);
}

export async function deleteBrand(id: string): Promise<void> {
  return api.delete(`/brands/${id}`);
}

export async function uploadBrandLogo(
  brandId: string,
  file: File
): Promise<Brand> {
  const formData = new FormData();
  formData.append("file", file);
  return api.post(`/brands/${brandId}/logo`, formData);
}
