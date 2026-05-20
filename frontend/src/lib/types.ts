// Shared TypeScript types — mirror the backend Pydantic schemas
// (services/*/app/models.py). Kept in sync by hand for now; a generated
// client is a future improvement.

export type Role = "Hospital" | "Donor" | "Courier" | "Doctor";

export type BloodType =
  | "O+"
  | "O-"
  | "A+"
  | "A-"
  | "B+"
  | "B-"
  | "AB+"
  | "AB-";

export type Urgency = "Critical" | "High" | "Standard";

export type MatchStatus = "Pending" | "Matched" | "NoMatch" | "Failed";

export type ItemType = "Blood" | "Organ";

export type InventoryStatus = "Available" | "Reserved" | "Dispatched";

export interface GeoLocation {
  lat: number;
  lng: number;
}

// --- Match service ---

export interface EmergencyRequestInput {
  hospital_id: string;
  blood_type: BloodType;
  units: number;
  urgency: Urgency;
  location: GeoLocation;
}

export interface MatchRecord {
  id: string;
  hospital_id: string;
  blood_type: BloodType;
  units: number;
  urgency: Urgency;
  location: GeoLocation;
  status: MatchStatus;
  matched_inventory_id: string | null;
  failure_reason: string | null;
  created_at: string;
  updated_at: string;
}

// --- Inventory service ---

export interface InventoryItemInput {
  hospital_id: string;
  item_type: ItemType;
  sub_type: string;
  expiry_date: string;
  location: GeoLocation;
}

export interface InventoryItem {
  id: string;
  hospital_id: string;
  item_type: ItemType;
  sub_type: string;
  expiry_date: string;
  status: InventoryStatus;
  location: GeoLocation;
  geohash: string;
  geohash_prefix: string;
  reserved_by: string | null;
  created_at: string;
  updated_at: string;
  distance_km?: number;
}

export interface InventoryQueryResult {
  count: number;
  geohash_prefix: string;
  items: InventoryItem[];
}

// --- Option lists for form selects ---

export const BLOOD_TYPES: BloodType[] = [
  "O+",
  "O-",
  "A+",
  "A-",
  "B+",
  "B-",
  "AB+",
  "AB-",
];

export const URGENCIES: Urgency[] = ["Critical", "High", "Standard"];

export const ITEM_TYPES: ItemType[] = ["Blood", "Organ"];
