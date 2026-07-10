const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface InventoryCheckResponse {
  found: boolean;
  status: 'unregistered' | 'booth_assigned' | 'activated' | 'not_in_inventory';
  booth_assigned_id?: number;
  first_activated_booth_id?: number;
  vehicle_plate?: string;
  vehicle_type?: string;
  can_activate?: boolean;
  activation_required?: boolean;
}

interface TagActivationQuickCreateRequest {
  tag_serial: string;
  tid: string;
  customer_name: string;
  customer_phone: string;
  initial_topup: number;
  payment_method: string;
  activation_booth_id: number;
}

interface TagActivationLinkExistingRequest {
  tag_serial: string;
  tid: string;
  account_id: string;
  activation_booth_id: number;
}

interface AccountSearchResult {
  id: string;
  user: {
    full_name: string;
    phone: string;
  };
  balance: number;
}

const getAuthHeaders = () => ({
  'Content-Type': 'application/json',
  Authorization: `Bearer ${localStorage.getItem('token')}`,
});

export const inventoryApi = {
  /**
   * Check if a tag is in unregistered inventory and get its status
   */
  async checkStatus(tagSerial: string): Promise<InventoryCheckResponse> {
    const response = await fetch(
      `${API_BASE}/api/v1/vehicles/inventory/check/${encodeURIComponent(tagSerial)}/`,
      {
        headers: getAuthHeaders(),
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to check inventory: ${response.statusText}`);
    }

    const data = await response.json();
    return data.data;
  },

  /**
   * Quick activation: Create new account and activate tag
   */
  async activateQuick(request: TagActivationQuickCreateRequest) {
    const response = await fetch(`${API_BASE}/api/v1/vehicles/inventory/activate/`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(request),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.message || 'Activation failed');
    }

    return data.data;
  },

  /**
   * Link tag to existing account
   */
  async activateExisting(request: TagActivationLinkExistingRequest) {
    const response = await fetch(`${API_BASE}/api/v1/vehicles/inventory/activate-existing/`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(request),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.message || 'Activation failed');
    }

    return data.data;
  },

  /**
   * Search for existing accounts by phone or name
   */
  async searchAccounts(query: string): Promise<AccountSearchResult[]> {
    const response = await fetch(`${API_BASE}/api/v1/accounts/search/?q=${encodeURIComponent(query)}`, {
      headers: getAuthHeaders(),
    });

    if (!response.ok) {
      return [];
    }

    const data = await response.json();
    return data.data?.items || [];
  },
};
