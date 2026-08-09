// ─── Legacy frontend types (kept for backwards compat with dummy data) ────────
export interface Vehicle {
  id: string;
  plateNumber: string;
  type: 'Car' | 'Truck' | 'Bus' | 'Motorcycle';
  model: string;
  company: string;
  status: 'Active' | 'Inactive';
  registeredAt: string;
  tagId: string;
}

export interface Transaction {
  id: string;
  vehicleId: string;
  vehiclePlate: string;
  plazaName: string;
  amount: number;
  date: string;
  vehicleClass: string;
  status: 'Completed' | 'Violation' | 'Pending';
}

export interface User {
  id: string;
  fullName: string;
  cnic: string;
  phone: string;
  email: string;
  avatar: string;
  balance: number;
}

export interface Toast {
  id: string;
  type: 'success' | 'error' | 'info';
  title: string;
  message?: string;
}

export interface MonthlyData {
  month: string;
  toll: number;
  transactions: number;
}

export interface DailyData {
  day: string;
  amount: number;
  count: number;
}

// ─── API types ────────────────────────────────────────────────────────────────
export interface ApiUser {
  id: number;
  uuid: string;
  full_name: string;
  phone: string;
  cnic?: string;
  user_role: string;
  status: string;
  created_at: string;
}

export interface Tag {
  id: number;
  tag_serial: string;
  issued_at: string;
  status: string;
  last_scanned_at?: string;
  is_valid: boolean;
}

export interface ApiVehicle {
  id: number;
  plate_number: string;
  vehicle_type: string;
  status: string;
  registered_at: string;
  owner_phone: string;
  owner_name: string;
  owner_id?: number;
  tag?: Tag;
}

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

export interface Lane {
  id: number;
  lane_number: number;
  is_active: boolean;
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

export interface TopupRequest {
  id: number;
  amount: string;
  status: string;
  jazzcash_txn_id?: string;
  requested_at: string;
  completed_at?: string;
}
