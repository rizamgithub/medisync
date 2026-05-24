import type { InventoryStatus, MatchStatus } from "@/lib/types";

const TONE: Record<string, string> = {
  Matched: "success",
  Available: "success",
  Pending: "info",
  NoMatch: "warning",
  Reserved: "warning",
  Failed: "danger",
  Dispatched: "neutral",
};

export function StatusBadge({
  status,
}: {
  status: MatchStatus | InventoryStatus;
}) {
  const tone = TONE[status] ?? "neutral";
  return <span className={`badge badge-${tone}`}>{status}</span>;
}
