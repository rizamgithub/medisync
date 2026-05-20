"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import {
  BLOOD_TYPES,
  URGENCIES,
  type BloodType,
  type Urgency,
} from "@/lib/types";

export default function RequestPage() {
  const router = useRouter();
  const [hospitalId, setHospitalId] = useState("HOSP-01");
  const [bloodType, setBloodType] = useState<BloodType>("O+");
  const [units, setUnits] = useState("1");
  const [urgency, setUrgency] = useState<Urgency>("Critical");
  const [lat, setLat] = useState("3.04");
  const [lng, setLng] = useState("101.45");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const result = await api.createEmergencyRequest({
        hospital_id: hospitalId.trim(),
        blood_type: bloodType,
        units: Number(units),
        urgency,
        location: { lat: Number(lat), lng: Number(lng) },
      });
      router.push(`/status?id=${encodeURIComponent(result.request_id)}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
      setSubmitting(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>New emergency request</h1>
        <p>Submit a request — the matching Saga starts immediately.</p>
      </div>

      <div className="card" style={{ maxWidth: 520 }}>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="hospital">Hospital ID</label>
            <input
              id="hospital"
              value={hospitalId}
              onChange={(e) => setHospitalId(e.target.value)}
              required
            />
          </div>

          <div className="field-row">
            <div className="field">
              <label htmlFor="blood">Blood type needed</label>
              <select
                id="blood"
                value={bloodType}
                onChange={(e) => setBloodType(e.target.value as BloodType)}
              >
                {BLOOD_TYPES.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="units">Units</label>
              <input
                id="units"
                type="number"
                min={1}
                max={100}
                value={units}
                onChange={(e) => setUnits(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="field">
            <label htmlFor="urgency">Urgency</label>
            <select
              id="urgency"
              value={urgency}
              onChange={(e) => setUrgency(e.target.value as Urgency)}
            >
              {URGENCIES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>

          <div className="field-row">
            <div className="field">
              <label htmlFor="lat">Latitude</label>
              <input
                id="lat"
                type="number"
                step="any"
                value={lat}
                onChange={(e) => setLat(e.target.value)}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="lng">Longitude</label>
              <input
                id="lng"
                type="number"
                step="any"
                value={lng}
                onChange={(e) => setLng(e.target.value)}
                required
              />
            </div>
          </div>

          {error && (
            <p className="notice notice-error" style={{ marginBottom: 14 }}>
              {error}
            </p>
          )}

          <button
            type="submit"
            className="btn btn-primary btn-lg"
            disabled={submitting}
          >
            {submitting ? "Submitting…" : "Submit request"}
          </button>
        </form>
      </div>
    </>
  );
}
