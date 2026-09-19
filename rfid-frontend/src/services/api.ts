export const BASE_URL = (import.meta.env.VITE_API_URL as string) || 'http://localhost:8000/api/v1';

// ─── Auth state helpers (display-only — no tokens stored in JS) ───────────────
export const clearAuthState = () => localStorage.removeItem('auth_user');

// ─── API response wrapper ─────────────────────────────────────────────────────
interface ApiResponse<T = unknown> {
  success: boolean;
  message: string;
  data: T;
  errors?: unknown;
}

export class ApiError extends Error {
  status?: number;
  errors?: Record<string, unknown>;
  constructor(message: string, errors?: Record<string, unknown>, status?: number) {
    super(message);
    this.name = 'ApiError';
    this.errors = errors;
    this.status = status;
  }
}

// ─── Token refresh (called automatically on 401) ──────────────────────────────
let _refreshPromise: Promise<boolean> | null = null;

async function tryRefreshToken(): Promise<boolean> {
  if (_refreshPromise) return _refreshPromise;
  _refreshPromise = fetch(`${BASE_URL}/auth/token/refresh/`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
  })
    .then((r) => r.ok)
    .catch(() => false)
    .finally(() => { _refreshPromise = null; });
  return _refreshPromise;
}

// ─── Core fetch wrapper ───────────────────────────────────────────────────────
// Tokens are httpOnly cookies — browser sends them automatically.
// On 401, we attempt a token refresh once before giving up.
export async function apiFetch<T>(endpoint: string, options: RequestInit = {}, isRetry = false): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (response.status === 401 && !isRetry) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      return apiFetch(endpoint, options, true);
    }
    clearAuthState();
    window.dispatchEvent(new CustomEvent('auth:expired'));
    throw new ApiError('Session expired. Please log in again.', undefined, 401);
  }

  const json: ApiResponse<T> = await response.json();

  if (!response.ok) {
    let message = json.message || `HTTP ${response.status}`;
    const errorsObj = json.errors && typeof json.errors === 'object'
      ? (json.errors as Record<string, unknown>)
      : undefined;
    if (errorsObj) {
      const details = Object.values(errorsObj)
        .flatMap((v) => (Array.isArray(v) ? v : [v]))
        .filter((v) => typeof v === 'string')
        .join(' ');
      if (details) message = `${message}: ${details}`;
    }
    throw new ApiError(message, errorsObj, response.status);
  }

  return json.data as T;
}

// ─── Auth types ───────────────────────────────────────────────────────────────
export interface LoginResponse {
  user_id: number;
  uuid: string;
  full_name: string;
  phone: string;
  role: string;
  // access / refresh tokens are set as httpOnly cookies by the server — not in body
}

export interface MeResponse {
  id: number;
  uuid: string;
  full_name: string;
  phone: string;
  cnic?: string;
  user_role: string;
  status: string;
  created_at: string;
}

// ─── Auth API ─────────────────────────────────────────────────────────────────
export const authApi = {
  login: (data: { phone: string; password: string }) =>
    apiFetch<LoginResponse>('/auth/login/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Cookies cleared server-side — no token body needed
  logout: () =>
    apiFetch<null>('/auth/logout/', { method: 'POST' }),

  me: () => apiFetch<MeResponse>('/auth/me/'),

  updateMe: (data: Partial<{ full_name: string; phone: string }>) =>
    apiFetch<MeResponse>('/auth/me/', {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  register: (data: { full_name: string; phone: string; cnic: string; password?: string }) =>
    apiFetch<unknown>('/auth/register/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  changePassword: (data: { old_password: string; new_password: string }) =>
    apiFetch<null>('/auth/change-password/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  adminUsers: (params?: { search?: string; role?: string; status?: string }) => {
    const qs = params
      ? '?' + new URLSearchParams(params as Record<string, string>).toString()
      : '';
    return apiFetch<MeResponse[]>(`/auth/admin/users/${qs}`);
  },

  adminUserDetail: (pk: number) => apiFetch<MeResponse>(`/auth/admin/users/${pk}/`),

  adminUpdateUser: (pk: number, data: Partial<MeResponse>) =>
    apiFetch<MeResponse>(`/auth/admin/users/${pk}/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
};

// ─── Vehicle types ────────────────────────────────────────────────────────────
export interface ApiVehicle {
  id: number;
  plate_number: string;
  vehicle_type: string;
  status: string;
  registered_at: string;
  owner_phone: string;
  owner_name: string;
  owner_id?: number;
  tag?: {
    id: number;
    tag_serial: string;
    issued_at: string;
    status: string;
    last_scanned_at?: string;
    is_valid: boolean;
  };
}

// ─── Vehicles API ─────────────────────────────────────────────────────────────
export const vehiclesApi = {
  list: (params?: { plate?: string }) => {
    const qs = params?.plate ? `?plate=${encodeURIComponent(params.plate)}` : '';
    return apiFetch<ApiVehicle[]>(`/vehicles/${qs}`);
  },

  create: (data: {
    plate_number: string;
    vehicle_type: string;
    owner_id: number;
    tag_serial: string;
    initial_balance?: number;
  }) => apiFetch<ApiVehicle>('/vehicles/', { method: 'POST', body: JSON.stringify(data) }),

  detail: (id: number) => apiFetch<ApiVehicle>(`/vehicles/${id}/`),

  update: (id: number, data: Partial<ApiVehicle>) =>
    apiFetch<ApiVehicle>(`/vehicles/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),

  byPlate: (plateNumber: string) => apiFetch<ApiVehicle>(`/vehicles/plate/${encodeURIComponent(plateNumber)}/`),

  reissueTag: (vehicleId: number, data: { tag_serial: string }) =>
    apiFetch<ApiVehicle['tag']>(`/vehicles/tags/${vehicleId}/reissue/`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  addTag: (data: { tag_serial: string; tid?: string; epc?: string }) =>
    apiFetch<{ id: number; tag_serial: string; tid: string | null; epc: string }>('/vehicles/tags/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  suspend: (vehicleId: number) =>
    apiFetch<ApiVehicle>(`/vehicles/${vehicleId}/suspend/`, {
      method: 'POST',
      body: JSON.stringify({ action: 'suspend' }),
    }),

  activate: (vehicleId: number) =>
    apiFetch<ApiVehicle>(`/vehicles/${vehicleId}/suspend/`, {
      method: 'POST',
      body: JSON.stringify({ action: 'activate' }),
    }),

  availableTags: (params?: { search?: string }) => {
    const qs = params?.search ? `?search=${encodeURIComponent(params.search)}` : '';
    return apiFetch<{ id: number; tag_serial: string; epc: string }[]>(`/vehicles/tags/available/${qs}`);
  },

  /** Identify a physically scanned tag. A reader reports a TID (sometimes only
   *  an EPC), never the printed serial, so this is what turns "the tag in my
   *  hand" into a serial the registration form can use. */
  scanLookup: (params: { tid?: string; epc?: string }) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v) as [string, string][]
    ).toString();
    return apiFetch<TagScanLookup>(`/vehicles/tags/scan-lookup/?${qs}`);
  },

  uploadTagInventory: async (file: File) => {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${BASE_URL}/vehicles/tags/upload/`, {
      method: 'POST',
      credentials: 'include',
      body: form,
    });
    const json = await res.json();
    if (!res.ok) throw new ApiError(json.message || `HTTP ${res.status}`);
    return json.data as { added: number; skipped: number; errors: string[]; skipped_serials: string[] };
  },
};

// ─── Daily report types ───────────────────────────────────────────────────────
export interface LaneReport {
  id: number | null;
  lane_number: number | null;
  is_active: boolean;
  entries: number;
  exits: number;
  revenue: number;
  vehicle_types: Record<string, number>;
}

export interface PlazaReport {
  id: number;
  plaza_id: number;
  name: string;
  is_active: boolean;
  entries: number;
  exits: number;
  revenue: number;
  lanes: LaneReport[];
}

export interface DailyReport {
  date: string;
  plazas: PlazaReport[];
  totals: { entries: number; exits: number; revenue: number };
}

// ─── Toll types ───────────────────────────────────────────────────────────────
export interface Lane {
  id: number;
  lane_number: number;
  is_active: boolean;
}

export interface Plaza {
  id: number;
  /** Operator-assigned plaza number (Plaza.plaza_id). Replaced `code`. */
  plaza_id: number;
  name: string;
  latitude?: string;
  longitude?: string;
  is_active: boolean;
  lanes: Lane[];
}

export interface TollRate {
  id: number;
  /** fare_matrix row. Field names mirror the table: from_plaza / to_plaza /
   *  category_index / fare. `category` IS the integer category_index. */
  from_plaza: number;
  from_plaza_name: string;
  from_plaza_display_id: string;
  to_plaza: number;
  to_plaza_name: string;
  to_plaza_display_id: string;
  category: number;
  category_name: string;
  category_code: string;
  fare: string;
  created_at: string;
  updated_at: string;
}

export interface VehicleCategory {
  id: number;
  category_index: number;
  code: string;
  name: string;
  description: string;
  is_active: boolean;
}

export interface TollTrip {
  id: number;
  plate_number: string;
  entry_plaza_name: string;
  exit_plaza_name?: string;
  entry_time: string;
  exit_time?: string;
  charge_amount?: string;
  balance_before?: string;
  balance_after?: string;
  status: string;
  duration_minutes?: number;
}

export interface StatsData {
  monthly: { month: string; toll: number; transactions: number }[];
  daily: { day: string; amount: number; count: number }[];
  vehicle_type_breakdown: { name: string; value: number; count: number }[];
  plaza_stats: { name: string; revenue: number; trips: number; is_active: boolean }[];
  total_vehicles: number;
  total_balance: number;
  active_plazas: number;
  total_trips: number;
  completed_trips: number;
  active_trips: number;
  total_revenue: number;
}

// ─── Tolls API ────────────────────────────────────────────────────────────────
export const tollsApi = {
  entry: (data: { tag_serial: string; plaza_id: number; lane_id?: number }) =>
    apiFetch<TollTrip>('/tolls/entry/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  exit: (data: { tag_serial: string; plaza_id: number; lane_id?: number }) =>
    apiFetch<TollTrip>('/tolls/exit/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  plazas: () => apiFetch<Plaza[]>('/tolls/plazas/'),

  rates: () => apiFetch<TollRate[]>('/tolls/rates/'),
  vehicleCategories: () => apiFetch<VehicleCategory[]>('/tolls/vehicle-categories/'),

  trips: (vehicleId: number) => apiFetch<TollTrip[]>(`/tolls/trips/${vehicleId}/`),

  adminTrips: (params?: { status?: string }) => {
    const qs = params?.status ? `?status=${params.status}` : '';
    return apiFetch<TollTrip[]>(`/tolls/admin/trips/${qs}`);
  },

  adminPlazas: () => apiFetch<Plaza[]>('/tolls/admin/plazas/'),

  adminCreatePlaza: (data: { name: string; plaza_id: number; latitude?: string; longitude?: string; is_active?: boolean }) =>
    apiFetch<Plaza>('/tolls/admin/plazas/', { method: 'POST', body: JSON.stringify(data) }),

  adminUpdatePlaza: (id: number, data: { is_active?: boolean; name?: string }) =>
    apiFetch<Plaza>(`/tolls/admin/plazas/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),

  adminLanes: (plazaId: number) => apiFetch<Lane[]>(`/tolls/admin/plazas/${plazaId}/lanes/`),

  adminCreateLane: (plazaId: number, data: { lane_number: number; is_active?: boolean }) =>
    apiFetch<Lane>(`/tolls/admin/plazas/${plazaId}/lanes/`, { method: 'POST', body: JSON.stringify(data) }),

  adminUpdateLane: (id: number, data: { lane_number?: number; is_active?: boolean }) =>
    apiFetch<Lane>(`/tolls/admin/lanes/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),

  adminDeleteLane: (id: number) =>
    apiFetch<null>(`/tolls/admin/lanes/${id}/`, { method: 'DELETE' }),

  adminCreateRate: (data: {
    from_plaza: number;
    to_plaza: number;
    category: number;
    fare: string;
  }) => apiFetch<TollRate>('/tolls/admin/rates/', { method: 'POST', body: JSON.stringify(data) }),

  adminUpdateRate: (id: number, data: {
    from_plaza?: number;
    to_plaza?: number;
    category?: number;
    fare?: string;
  }) => apiFetch<TollRate>(`/tolls/admin/rates/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),

  adminDeleteRate: (id: number) =>
    apiFetch<null>(`/tolls/admin/rates/${id}/`, { method: 'DELETE' }),

  adminDeletePlaza: (id: number) =>
    apiFetch<null>(`/tolls/admin/plazas/${id}/`, { method: 'DELETE' }),

  stats: () => apiFetch<StatsData>('/tolls/admin/stats/'),

  closeTrip: (tripId: number) =>
    apiFetch<TollTrip>(`/tolls/admin/trips/${tripId}/close/`, { method: 'POST' }),

  refundTrip: (tripId: number) =>
    apiFetch<{ trip_id: number; plate_number: string; refunded_amount: string; new_balance: string }>(
      `/tolls/admin/trips/${tripId}/refund/`, { method: 'POST' }
    ),

  dailyReport: (date?: string) => {
    const qs = date ? `?date=${date}` : '';
    return apiFetch<DailyReport>(`/tolls/admin/daily-report/${qs}`);
  },

  gateEvents: (params?: { pending?: boolean }) => {
    const qs = params?.pending ? '?pending=1' : '';
    return apiFetch<{ id: number; plaza: string; lane: number | null; created_at: string; executed_at: string | null; status: string }[]>(
      `/tolls/admin/gate-events/${qs}`
    );
  },
};

// ─── Booth code deployment ────────────────────────────────────────────────────
export interface BoothJobBrief {
  id: number;
  action: 'check' | 'update';
  status: 'pending' | 'running' | 'succeeded' | 'failed';
  requested_at: string;
  started_at: string | null;
  finished_at: string | null;
}

/** One lane's booth machine. `id` is null for a lane with no machine configured
 *  yet — those rows still come back so the operator can add one. */
export interface BoothDeployment {
  id: number | null;
  lane: number;
  lane_number: number;
  lane_is_active?: boolean;
  plaza_id: number;
  plaza_name: string;
  plaza_display_id: string;
  host: string;
  ssh_port?: number;
  ssh_user?: string;
  ssh_user_effective?: string;
  reported_version: string;
  pm2_summary?: string;
  reachable: boolean | null;
  last_error?: string;
  last_checked_at?: string | null;
  last_deployed_at?: string | null;
  active_job: BoothJobBrief | null;
}

export interface BoothDeployJob extends BoothJobBrief {
  machine: number;
  lane_number: number;
  requested_by_name?: string;
  from_version: string;
  to_version: string;
  exit_code: number | null;
  log: string;
}

export interface BoothDeployJobSummary {
  id: number;
  machine: number;
  lane_number: number;
  plaza_name: string;
  action: 'check' | 'update';
  status: 'pending' | 'running' | 'succeeded' | 'failed';
  requested_by_name?: string;
  requested_at: string;
  finished_at: string | null;
  from_version: string;
  to_version: string;
  exit_code: number | null;
}

export interface TagScanLookup {
  tid: string;
  epc: string;
  tag_serial: string | null;
  in_inventory: boolean;
  available: boolean;
  status:
    | 'available'
    | 'in_inventory'
    | 'already_issued'
    | 'already_activated'
    | 'tag_not_active'
    | 'not_in_inventory';
  message: string;
  assigned_plate?: string;
  booth_assigned_id?: number | null;
}

export const boothsApi = {
  deployments: () =>
    apiFetch<{ master_version: string; booths: BoothDeployment[] }>('/tolls/admin/booth-deployments/'),

  saveMachine: (data: { lane: number; host: string; ssh_port?: number; ssh_user?: string }) =>
    apiFetch<BoothDeployment>('/tolls/admin/booth-deployments/', {
      method: 'POST', body: JSON.stringify(data),
    }),

  deleteMachine: (id: number) =>
    apiFetch<null>(`/tolls/admin/booth-machines/${id}/`, { method: 'DELETE' }),

  queueJob: (machineId: number, action: 'check' | 'update') =>
    apiFetch<BoothDeployJob>(`/tolls/admin/booth-machines/${machineId}/jobs/`, {
      method: 'POST', body: JSON.stringify({ action }),
    }),

  job: (id: number) => apiFetch<BoothDeployJob>(`/tolls/admin/booth-jobs/${id}/`),

  jobHistory: () => apiFetch<BoothDeployJobSummary[]>('/tolls/admin/booth-jobs/'),
};

// ─── Account types ────────────────────────────────────────────────────────────
export interface Account {
  id: number;
  plate_number: string;
  vehicle_type: string;
  balance: string;
  balance_updated_at: string;
  created_at: string;
}

export interface ApiTransaction {
  id: number;
  transaction_type: string;
  amount: string;
  balance_before: string;
  balance_after: string;
  status: string;
  tag_serial?: string;
  processed_at: string;
  description?: string;
}

export interface TransferResult {
  transferred_amount: string;
  source_vehicle: string;
  target_vehicle: string;
  reference_id: string;
}

// ─── Topup types ─────────────────────────────────────────────────────────────
export interface TopupLookupResult {
  found: boolean;
  tid: string;
  epc: string;
  consumer_name?: string;
  cnic?: string;
  phone?: string;
  plate?: string;
  balance?: string;
  inventory_status?: 'unregistered' | 'booth_assigned' | 'activated';
  booth_assigned_id?: number | null;
}

export interface CashTopupReceipt {
  receipt_no: string;
  datetime: string;
  consumer_name: string;
  vehicle_reg: string;
  tid: string;
  amount: string;
  balance_before: string;
  balance_after: string;
  payment: string;
  operator: string;
}

export interface CashTopupResult {
  registered: boolean;
  consumer_name: string;
  plate?: string;
  amount_added: string;
  new_balance: string;
  printed?: boolean;
  receipt?: CashTopupReceipt;
}

// ─── Accounts API ─────────────────────────────────────────────────────────────
export const accountsApi = {
  byVehicle: (vehicleId: number) => apiFetch<Account>(`/accounts/vehicle/${vehicleId}/`),

  transactions: (accountId: number, params?: { type?: string; page?: number }) => {
    const qs = params
      ? '?' + new URLSearchParams(params as Record<string, string>).toString()
      : '';
    return apiFetch<{ results: ApiTransaction[]; count: number; next?: string; previous?: string }>(
      `/accounts/${accountId}/transactions/${qs}`
    );
  },

  adminAll: () => apiFetch<Account[]>('/accounts/admin/all/'),

  operatorTopup: (tag_serial: string, amount: number) =>
    apiFetch<{ plate_number: string; amount_added: string; new_balance: string }>(
      '/accounts/operator/topup/',
      { method: 'POST', body: JSON.stringify({ tag_serial, amount }) }
    ),

  plateTopup: (plate_number: string, amount: number) =>
    apiFetch<{ plate_number: string; vehicle_type: string; amount_added: string; balance_before: string; new_balance: string }>(
      '/accounts/topup/plate/',
      { method: 'POST', body: JSON.stringify({ plate_number, amount }) }
    ),

  topupLookup: (tid: string) =>
    apiFetch<TopupLookupResult>('/accounts/topup/lookup/', {
      method: 'POST',
      body: JSON.stringify({ tid }),
    }),

  cashTopup: (payload: {
    tid: string;
    amount: string;
    epc?: string;
    consumer_name?: string;
    cnic?: string;
    phone?: string;
    vehicle_reg?: string;
    activation_booth_id?: number;
  }) =>
    apiFetch<CashTopupResult>('/accounts/topup/cash/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  transferBalance: (data: {
    source_vehicle_id: number;
    target_vehicle_id: number;
    cnic: string;
    phone: string;
    name: string;
  }) =>
    apiFetch<TransferResult>('/accounts/transfer/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ─── Payment types ────────────────────────────────────────────────────────────
export interface TopupRequest {
  id: number;
  amount: string;
  status: string;
  jazzcash_txn_id?: string;
  requested_at: string;
  completed_at?: string;
}

// ─── Payments API ─────────────────────────────────────────────────────────────
export const paymentsApi = {
  initiate: (data: { account_id: number; amount: number }) =>
    apiFetch<TopupRequest>('/payments/topup/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  callback: (data: { pp_TxnRefNo: string; pp_ResponseCode: string; topup_id: number }) =>
    apiFetch<TopupRequest>('/payments/jazzcash/callback/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  history: (accountId: number) =>
    apiFetch<TopupRequest[]>(`/payments/history/${accountId}/`),
};
