> ## ⚠️ Azure Edition (2026-05-19)
> Tech references in §2 below have been ported from the original AWS stack to Azure. The narrative (Golden Hour, actors, flow) is unchanged. See `context.md` for the full service map.

To make this project stand out in your portfolio, you need a **compelling, real-world narrative.** Here is a detailed Use Case for **MediSync**, broken down by the actors involved and the technical flow.

---

### Use Case Title: "The Golden Hour" Emergency Fulfillment

**The Scenario:** 
A major traffic accident occurs. "City General Hospital" receives a patient needing an emergency transfusion of **O-Negative blood** (a rare type). The hospital’s internal blood bank is empty.

---

### 1. The Actors
*   **The Requester:** A verified Hospital Administrator or Doctor.
*   **The Donor:** A registered citizen with a matching blood type within a 10km radius.
*   **The Courier:** A logistics partner (or ambulance driver) responsible for transport.
*   **The System (MediSync):** The microservice orchestrator managing the logic.

---

### 2. The Step-by-Step Workflow

#### Step A: The Emergency Trigger (The Request Service)
*   **Action:** Dr. Sarah logs into the MediSync dashboard and hits the "Emergency Request" button for 3 units of O-Negative blood.
*   **Technical Flow:** The **Request Service** (Python on Azure Functions) validates the hospital's JWT via **Entra External ID** and writes the request to **Cosmos DB**.
*   **Event:** It emits an `EmergencyRequestCreated` event to **Azure Event Grid**.

#### Step B: Automated Inventory Search (The Inventory Service)
*   **Action:** The system automatically polls all hospitals within a 20-mile radius to see if they have surplus O-Negative blood.
*   **Technical Flow:** The **Inventory Service** (Azure Functions, Event Grid trigger) receives the event. It queries its Cosmos DB container for nearby hospital IDs with stock > 3 units using a geohash-prefix partition key.
*   **Result:** "Mercy Hospital" (5 miles away) has the stock. A reservation is placed via a Cosmos DB conditional write (ETag / If-Match) so that blood isn't given to anyone else during the transit.

#### Step C: The "Human Gap" (The Matching & Notification Service)
*   **Scenario:** What if no hospitals have stock?
*   **Action:** The **Matching Service** (Durable Functions orchestrator) triggers a "Broadcast" to nearby eligible donors.
*   **Technical Flow:** The orchestrator calculates geo-coordinates using geohash prefixes over the Cosmos DB index. It identifies 50 donors nearby. It sends an email via **Azure Communication Services — Email**. (SMS / push notifications are Phase 2 — would use ACS SMS + Notification Hubs.)
*   **Donor Response:** A donor named John accepts the request on his phone.

#### Step D: Secure Logistics (The Tracking Service — Phase 2)
*   **Action:** A courier picks up the blood from Mercy Hospital (or John goes to a clinic).
*   **Technical Flow:** The **Logistics Service** creates a "Live Trip." The courier's mobile app sends GPS coordinates every 30 seconds via an **Azure SignalR Service** WebSocket connection (replaces the original AppSync/IoT Core idea — cheaper and scales to zero on free tier).
*   **Real-time Update:** Dr. Sarah at the receiving hospital sees a live map (Leaflet + OpenStreetMap, SignalR client) showing the blood is 4 minutes away.

#### Step E: Completion & Ledger (The Analytics Service — Phase 3)
*   **Action:** The blood arrives, is scanned (QR code), and the request is marked "Fulfilled."
*   **Technical Flow:** An `OrderCompleted` event is sent. The **Analytics Service** logs this for a monthly report. An Azure Function calculates the "Time-to-Delivery" and saves it to **Blob Storage (Cool tier)** for long-term auditing. Aggregations queried via **Azure Data Explorer (Kusto)** free cluster or simply via Application Insights KQL over the event log.

---

### 3. Why this is "Brilliant" for your Portfolio

When an interviewer asks, *"Why did you build this?"* you explain the **Business Value**:

1.  **Solving the "Silo" Problem:** Currently, Hospital A doesn't know what Hospital B has in stock. Your app creates a **Unified Inventory**.
2.  **Removing Human Latency:** Instead of a nurse spending 30 minutes on the phone calling other hospitals, your **Event-Driven Architecture** finds the blood in milliseconds.
3.  **Data-Driven Decisions:** You can show a "Heatmap" of blood shortages, allowing the government to run blood drives in specific neighborhoods before an emergency happens.

---

### 4. Technical "Edge Cases" to handle (Interview Prep)
To show you are a Senior-level thinker, be prepared to answer how your system handles these:
*   **The "Race Condition":** What if two hospitals try to claim the last unit of blood at the exact same time? (Solution: **Cosmos DB optimistic concurrency via ETag / If-Match** — replaces DynamoDB conditional writes from the AWS version.)
*   **Offline Support:** What if the courier enters a tunnel and loses GPS? (Solution: client-side queue of position updates flushed on reconnect; the SignalR backplane preserves last-known state in Cosmos.)
*   **Security:** How do you protect Donor health data? (Solution: **field-level encryption** using **Azure Key Vault** keys via the Cosmos DB client-side encryption SDK; key access gated by Managed Identity + Key Vault RBAC.)

### Your Next Step:
Would you like a **High-Level Architecture Diagram** description or a **Database Schema** for the "Inventory Service" to get started?


#### Please Add or enhance this use case when needed.