import { apiFetch, BASE_URL } from './api';

export interface InventoryItem {
  id: string;
  tag_serial: string;
  tid: string;
  vehicle_plate: string;
  vehicle_type: string;
  status: 'unregistered' | 'booth_assigned' | 'activated';
  booth_assigned_id?: number;
  first_activated_booth_id?: number;
  created_at: string;
}

export interface InventoryListResult {
  items: InventoryItem[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface InventoryCheckResponse {
  found: boolean;
  tid?: string;
  status: 'unregistered' | 'booth_assigned' | 'activated' | 'not_in_inventory';
  booth_assigned_id?: number;
  first_activated_booth_id?: number;
  vehicle_plate?: string;
  vehicle_type?: string;
  can_activate?: boolean;
  activation_required?: boolean;
}

export interface InventoryListParams {
  page?: number;
  per_page?: number;
  search?: string;
  status?: string;
  booth_assigned_id?: string | number;
  vehicle_type?: string;
}

export const inventoryApi = {
  list: (params: InventoryListParams = {}) => {
    const qs = new URLSearchParams();
    if (params.page) qs.append('page', String(params.page));
    if (params.per_page) qs.append('per_page', String(params.per_page));
    if (params.search) qs.append('search', params.search);
    if (params.status) qs.append('status', params.status);
    if (params.booth_assigned_id) qs.append('booth_assigned_id', String(params.booth_assigned_id));
    if (params.vehicle_type) qs.append('vehicle_type', params.vehicle_type);
    return apiFetch<InventoryListResult>(`/vehicles/inventory/?${qs.toString()}`);
  },

  checkStatus: (tagSerial: string) =>
    apiFetch<InventoryCheckResponse>(
      `/vehicles/inventory/check/${encodeURIComponent(tagSerial)}/`,
    ),

  assignBooth: (payload: { inventory_ids: string[]; booth_id: number; assigned_by?: string }) =>
    apiFetch<{ assigned: number }>('/vehicles/inventory/assign-booth/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // Multipart upload: apiFetch always sets JSON Content-Type, so use raw fetch
  // with credentials so the httpOnly auth cookie is sent (matches vehiclesApi.uploadTagInventory).
  upload: async (file: File): Promise<{ added: number; skipped: number; errors: string[] }> => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${BASE_URL}/vehicles/inventory/upload/`, {
      method: 'POST',
      credentials: 'include',
      body: formData,
    });
    const json = await res.json();
    if (!res.ok) {
      throw new Error(json.message || 'Upload failed');
    }
    return json.data;
  },
};
