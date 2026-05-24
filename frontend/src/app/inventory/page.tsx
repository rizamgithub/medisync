"use client";

import { useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import {
  BLOOD_TYPES,
  ITEM_TYPES,
  type InventoryItem,
  type ItemType,
} from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";

export default function InventoryPage() {
  // --- region search ---
  const [qLat, setQLat] = useState("3.04");
  const [qLng, setQLng] = useState("101.45");
  const [qRadius, setQRadius] = useState("5");
  const [qSubType, setQSubType] = useState("");
  const [results, setResults] = useState<InventoryItem[] | null>(null);
  const [querying, setQuerying] = useState(false);
  const [queryError, setQueryError] = useState<string | null>(null);

  // --- register stock ---
  const [aHospital, setAHospital] = useState("HOSP-01");
  const [aItemType, setAItemType] = useState<ItemType>("Blood");
  const [aSubType, setASubType] = useState("O+");
  const [aExpiry, setAExpiry] = useState("");
  const [aLat, setALat] = useState("3.04");
  const [aLng, setALng] = useState("101.45");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [addOk, setAddOk] = useState<string | null>(null);

  async function runQuery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setQueryError(null);
    setQuerying(true);
    try {
      const result = await api.queryInventory(
        Number(qLat),
        Number(qLng),
        Number(qRadius),
        qSubType.trim() || undefined,
      );
      setResults(result.items);
    } catch (err) {
      setQueryError(err instanceof ApiError ? err.message : "Query failed.");
      setResults(null);
    } finally {
      setQuerying(false);
    }
  }

  async function runAdd(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAddError(null);
    setAddOk(null);
    setAdding(true);
    try {
      const item = await api.addInventory({
        hospital_id: aHospital.trim(),
        item_type: aItemType,
        sub_type: aSubType.trim(),
        expiry_date: aExpiry,
        location: { lat: Number(aLat), lng: Number(aLng) },
      });
      setAddOk(`Added ${item.item_type} unit ${item.id}.`);
    } catch (err) {
      setAddError(
        err instanceof ApiError ? err.message : "Could not add stock.",
      );
    } finally {
      setAdding(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>Inventory</h1>
        <p>Search Available stock by region, or register a new unit.</p>
      </div>

      <div className="card">
        <h2>Find stock near a location</h2>
        <p className="card-hint">
          Resolves the geohash prefix, queries that single partition, then ranks
          results by distance.
        </p>
        <form onSubmit={runQuery}>
          <div className="field-row">
            <div className="field">
              <label htmlFor="qlat">Latitude</label>
              <input
                id="qlat"
                type="number"
                step="any"
                value={qLat}
                onChange={(e) => setQLat(e.target.value)}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="qlng">Longitude</label>
              <input
                id="qlng"
                type="number"
                step="any"
                value={qLng}
                onChange={(e) => setQLng(e.target.value)}
                required
              />
            </div>
          </div>
          <div className="field-row">
            <div className="field">
              <label htmlFor="qradius">Radius (km)</label>
              <input
                id="qradius"
                type="number"
                step="any"
                min={1}
                max={50}
                value={qRadius}
                onChange={(e) => setQRadius(e.target.value)}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="qsub">Sub-type (optional)</label>
              <input
                id="qsub"
                placeholder="e.g. O- or Kidney"
                value={qSubType}
                onChange={(e) => setQSubType(e.target.value)}
              />
            </div>
          </div>
          <button type="submit" className="btn btn-primary" disabled={querying}>
            {querying ? "Searching…" : "Search"}
          </button>
        </form>

        {queryError && (
          <p className="notice notice-error" style={{ marginTop: 14 }}>
            {queryError}
          </p>
        )}

        {results && !queryError && (
          <div style={{ marginTop: 16 }}>
            {results.length === 0 ? (
              <p className="muted">No Available stock in range.</p>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Sub-type</th>
                    <th>Hospital</th>
                    <th>Distance</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((item) => (
                    <tr key={item.id}>
                      <td>{item.item_type}</td>
                      <td>{item.sub_type}</td>
                      <td>{item.hospital_id}</td>
                      <td>
                        {item.distance_km != null
                          ? `${item.distance_km} km`
                          : "—"}
                      </td>
                      <td>
                        <StatusBadge status={item.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      <div className="card">
        <h2>Register a unit of stock</h2>
        <p className="card-hint">
          The geohash is computed server-side from the location.
        </p>
        <form onSubmit={runAdd}>
          <div className="field">
            <label htmlFor="ahospital">Hospital ID</label>
            <input
              id="ahospital"
              value={aHospital}
              onChange={(e) => setAHospital(e.target.value)}
              required
            />
          </div>
          <div className="field-row">
            <div className="field">
              <label htmlFor="aitem">Item type</label>
              <select
                id="aitem"
                value={aItemType}
                onChange={(e) => {
                  const next = e.target.value as ItemType;
                  setAItemType(next);
                  setASubType(next === "Blood" ? "O+" : "");
                }}
              >
                {ITEM_TYPES.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="asub">Sub-type</label>
              {aItemType === "Blood" ? (
                <select
                  id="asub"
                  value={aSubType}
                  onChange={(e) => setASubType(e.target.value)}
                >
                  {BLOOD_TYPES.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  id="asub"
                  placeholder="e.g. Kidney"
                  value={aSubType}
                  onChange={(e) => setASubType(e.target.value)}
                  required
                />
              )}
            </div>
          </div>
          <div className="field">
            <label htmlFor="aexpiry">Expiry date</label>
            <input
              id="aexpiry"
              type="date"
              value={aExpiry}
              onChange={(e) => setAExpiry(e.target.value)}
              required
            />
          </div>
          <div className="field-row">
            <div className="field">
              <label htmlFor="alat">Latitude</label>
              <input
                id="alat"
                type="number"
                step="any"
                value={aLat}
                onChange={(e) => setALat(e.target.value)}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="alng">Longitude</label>
              <input
                id="alng"
                type="number"
                step="any"
                value={aLng}
                onChange={(e) => setALng(e.target.value)}
                required
              />
            </div>
          </div>

          {addError && (
            <p className="notice notice-error" style={{ marginBottom: 14 }}>
              {addError}
            </p>
          )}
          {addOk && (
            <p className="notice notice-success" style={{ marginBottom: 14 }}>
              {addOk}
            </p>
          )}

          <button type="submit" className="btn btn-primary" disabled={adding}>
            {adding ? "Adding…" : "Add stock"}
          </button>
        </form>
      </div>
    </>
  );
}
