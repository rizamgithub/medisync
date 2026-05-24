import Link from "next/link";

const CAPABILITIES = [
  {
    title: "Emergency Matching",
    body: "A Durable Functions Saga finds, reserves and confirms a compatible unit — and compensates automatically if any step fails.",
  },
  {
    title: "Geo Inventory",
    body: "Blood and organ stock is geohash-bucketed in Cosmos DB, so a regional search resolves to a single partition.",
  },
  {
    title: "Event-Driven",
    body: "Services stay decoupled through Event Grid — requests, matches and releases all flow as typed domain events.",
  },
];

export default function DashboardPage() {
  return (
    <>
      <section className="hero">
        <h1>Emergency blood and organ supply matching</h1>
        <p>
          MediSync connects hospitals in critical need with the nearest
          compatible supply — an event-driven platform built on Azure
          serverless.
        </p>
        <Link href="/request" className="btn btn-primary btn-lg">
          Open an emergency request
        </Link>
      </section>

      <div className="grid">
        {CAPABILITIES.map((capability) => (
          <div key={capability.title} className="card">
            <h2>{capability.title}</h2>
            <p className="muted">{capability.body}</p>
          </div>
        ))}
      </div>

      <div className="card" style={{ marginTop: 20 }}>
        <h2>How a request flows</h2>
        <ol className="muted stack-sm">
          <li>A hospital submits an emergency request.</li>
          <li>
            The match service publishes{" "}
            <span className="mono">MediSync.EmergencyRequestCreated</span> to
            Event Grid.
          </li>
          <li>
            A Durable Functions orchestrator runs the Saga: find → reserve →
            notify → complete.
          </li>
          <li>
            On any failure it compensates — releasing the reservation and
            recording the outcome.
          </li>
        </ol>
        <p className="muted" style={{ marginTop: 14 }}>
          Start one from <Link href="/request">New Request</Link>, or seed and
          browse stock under <Link href="/inventory">Inventory</Link>.
        </p>
      </div>
    </>
  );
}
