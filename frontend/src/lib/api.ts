// Typed client for the MediSync Function App APIs.
//
// Base URLs are read from NEXT_PUBLIC_* env vars, inlined at build time
// (see .env.example). The Function Apps use ANONYMOUS auth for now — once
// Entra External ID exists, attach the bearer token here (TODO(entra)).

import type {
  EmergencyRequestInput,
  InventoryItem,
  InventoryItemInput,
  InventoryQueryResult,
  MatchRecord,
} from "./types";

const MATCH_API =
  process.env.NEXT_PUBLIC_MATCH_API_URL ?? "http://localhost:7071";
const INVENTORY_API =
  process.env.NEXT_PUBLIC_INVENTORY_API_URL ?? "http://localhost:7072";

/** Error carrying the HTTP status (0 = the service could not be reached). */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function send<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "Could not reach the service — is it running?");
  }

  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { error?: string };
      if (body.error) message = body.error;
    } catch {
      // response carried no JSON body — keep the status-line message
    }
    throw new ApiError(res.status, message);
  }

  return (await res.json()) as T;
}

export const api = {
  /** Submit an emergency request — returns 202 with the new request id. */
  createEmergencyRequest(input: EmergencyRequestInput) {
    return send<{ request_id: string; status: string }>(
      `${MATCH_API}/api/request/emergency`,
      { method: "POST", body: JSON.stringify(input) },
    );
  },

  /** Fetch a request and its current Saga outcome. */
  getRequest(id: string) {
    return send<MatchRecord>(
      `${MATCH_API}/api/request/${encodeURIComponent(id)}`,
    );
  },

  /** Find Available stock near a point. */
  queryInventory(
    lat: number,
    lng: number,
    radiusKm: number,
    subType?: string,
  ) {
    const params = new URLSearchParams({
      lat: String(lat),
      lng: String(lng),
      radius_km: String(radiusKm),
    });
    if (subType) params.set("sub_type", subType);
    return send<InventoryQueryResult>(
      `${INVENTORY_API}/api/inventory?${params.toString()}`,
    );
  },

  /** Register a new unit of stock. */
  addInventory(input: InventoryItemInput) {
    return send<InventoryItem>(`${INVENTORY_API}/api/inventory`, {
      method: "POST",
      body: JSON.stringify(input),
    });
  },
};
