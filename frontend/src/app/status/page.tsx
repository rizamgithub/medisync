"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import type { MatchRecord } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";

function StatusView() {
  const id = useSearchParams().get("id");
  const [record, setRecord] = useState<MatchRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function poll(requestId: string) {
      try {
        const next = await api.getRequest(requestId);
        if (!active) return;
        setRecord(next);
        setError(null);
        // Keep polling only while the Saga is still running.
        if (next.status === "Pending") {
          timer = setTimeout(() => poll(requestId), 2500);
        }
      } catch (err) {
        if (!active) return;
        setError(
          err instanceof Error ? err.message : "Failed to load request.",
        );
      }
    }

    poll(id);
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [id]);

  if (!id) {
    return (
      <p className="notice">
        No request id supplied. <Link href="/request">Create a request</Link>.
      </p>
    );
  }
  if (error) {
    return <p className="notice notice-error">{error}</p>;
  }
  if (!record) {
    return <p className="notice">Loading request…</p>;
  }

  return (
    <div className="card">
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <h2 style={{ margin: 0 }}>Request outcome</h2>
        <StatusBadge status={record.status} />
      </div>

      <dl className="detail-grid" style={{ marginTop: 16 }}>
        <dt>Request ID</dt>
        <dd className="mono">{record.id}</dd>
        <dt>Hospital</dt>
        <dd>{record.hospital_id}</dd>
        <dt>Blood type</dt>
        <dd>{record.blood_type}</dd>
        <dt>Units</dt>
        <dd>{record.units}</dd>
        <dt>Urgency</dt>
        <dd>{record.urgency}</dd>
        <dt>Location</dt>
        <dd>
          {record.location.lat}, {record.location.lng}
        </dd>
        <dt>Matched unit</dt>
        <dd>{record.matched_inventory_id ?? "—"}</dd>
        {record.failure_reason && (
          <>
            <dt>Reason</dt>
            <dd>{record.failure_reason}</dd>
          </>
        )}
        <dt>Updated</dt>
        <dd>{new Date(record.updated_at).toLocaleString()}</dd>
      </dl>

      {record.status === "Pending" && (
        <p className="muted" style={{ marginTop: 14 }}>
          The Saga is running — this page refreshes automatically.
        </p>
      )}
    </div>
  );
}

export default function StatusPage() {
  return (
    <>
      <div className="page-head">
        <h1>Request status</h1>
        <p>Live outcome of the matching Saga.</p>
      </div>
      <Suspense fallback={<p className="notice">Loading…</p>}>
        <StatusView />
      </Suspense>
    </>
  );
}
