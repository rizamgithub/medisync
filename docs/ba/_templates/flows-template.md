# Flows & Diagrams — {{Feature Name}}

| Field | Value |
|---|---|
| Feature ID | `NN-feature-slug` |
| Related BRD | [`brd.md`](./brd.md) |
| Related FSD | [`fsd.md`](./fsd.md) |
| Last updated | YYYY-MM-DD |

> All diagrams use **Mermaid** as the source of truth and are also exported
> to SVG (see `docs/ba/README.md` → "Diagram rendering"). After editing
> any block below, run `npm run render:diagrams` from the repo root to
> refresh the sibling `flows/*.svg` files.
>
> Section numbering doubles as the filename prefix — `## 3. X` renders to
> `flows/03-x.svg`. Keep section numbers stable when adding diagrams later.

---

## 0. Use Case Diagram

Classic UML view: actors (boxes) interact with use cases (ovals) inside the system boundary. Use `«include»` for behavior another use case always invokes, `«extend»` for optional/conditional extension.

```mermaid
flowchart LR
    ActorA(["Actor A<br/>(human)"])
    ActorB(["Actor B<br/>(human)"])

    subgraph System["{{Feature Name}}"]
        direction TB
        UC1(("UC-01<br/>Do thing"))
        UC2(("UC-02<br/>Do other thing"))
        UCInc(("Shared step<br/>e.g. authenticate"))
    end

    External(["External System<br/>(supporting actor)"])

    ActorA --- UC1
    ActorA --- UC2
    ActorB --- UC2

    UC1 -.->|"«include»"| UCInc
    UC2 -.->|"«include»"| UCInc

    UC1 --- External

    classDef actor fill:#fef3c7,stroke:#92400e,stroke-width:1px,color:#000;
    classDef usecase fill:#dbeafe,stroke:#1e40af,stroke-width:1px,color:#000;
    classDef support fill:#fce7f3,stroke:#9d174d,stroke-width:1px,color:#000;
    class ActorA,ActorB actor;
    class UC1,UC2,UCInc usecase;
    class External support;
```

![Use case diagram](./flows/00-use-case-diagram.svg)

---

## 1. Context Diagram

Shows the feature as a black box with its external actors and systems.

```mermaid
graph LR
    Hospital[Hospital User]
    Donor[Donor User]
    Feature{{This Feature}}
    EntraID[(Entra External ID)]
    Cosmos[(Cosmos DB)]
    EventGrid[(Event Grid)]

    Hospital -->|HTTPS + JWT| Feature
    Donor -->|HTTPS + JWT| Feature
    Feature -->|validate token| EntraID
    Feature -->|read/write| Cosmos
    Feature -->|publish events| EventGrid
```

![Context diagram](./flows/01-context-diagram.svg)

## 2. Process Flow (Business Process)

Business-level steps. Swimlanes by actor.

```mermaid
flowchart TD
    Start([Start]) --> A[Hospital submits request]
    A --> B{Valid?}
    B -- No --> X[Show validation error]
    B -- Yes --> C[System creates request]
    C --> D[System publishes EmergencyRequestCreated]
    D --> E[Match service starts saga]
    E --> F{Match found?}
    F -- Yes --> G[Notify hospital + courier]
    F -- No --> H[Notify hospital — no match]
    G --> End([End])
    H --> End
    X --> End
```

![Process flow](./flows/02-process-flow-business-process.svg)

## 3. Sequence Diagram (Technical)

Shows the order of calls between components.

```mermaid
sequenceDiagram
    autonumber
    actor User as Hospital
    participant FE as Frontend (Next.js)
    participant Entra as Entra External ID
    participant API as Match Function
    participant DB as Cosmos DB
    participant EG as Event Grid

    User->>FE: Submit request form
    FE->>Entra: Acquire token (MSAL)
    Entra-->>FE: Access token
    FE->>API: POST /requests + JWT
    API->>API: Validate JWT + role
    API->>DB: Insert request item
    DB-->>API: 201 + _etag
    API->>EG: Publish EmergencyRequestCreated
    EG-->>API: 200
    API-->>FE: 201 { request_id }
    FE-->>User: Confirmation
```

![Sequence diagram](./flows/03-sequence-diagram-technical.svg)

## 4. State Diagram (optional — add if entity has lifecycle)

```mermaid
stateDiagram-v2
    [*] --> Pending
    Pending --> Matching: EmergencyRequestCreated
    Matching --> Reserved: MatchFound
    Matching --> Failed: MatchFailed
    Reserved --> Delivered: DeliveryConfirmed
    Reserved --> Released: ReservationReleased
    Delivered --> [*]
    Failed --> [*]
    Released --> Pending: retry
```

![State diagram](./flows/04-state-diagram-optional-add-if-entity-has-lifecycle.svg)

## 5. Data Flow Diagram (optional)

```mermaid
flowchart LR
    subgraph External
        H[Hospital]
    end
    subgraph System
        P1((1.0 Validate Request))
        P2((2.0 Persist Request))
        P3((3.0 Publish Event))
    end
    subgraph Stores
        D1[(Requests Container)]
        D2[(Event Grid Topic)]
    end

    H -->|request payload| P1
    P1 -->|validated| P2
    P2 -->|write| D1
    P2 -->|request_id| P3
    P3 -->|event| D2
```

![Data flow](./flows/05-data-flow-diagram-optional.svg)

## 6. Notes

- Add links to App Insights screenshots / Application Map images once implemented.
- Update diagrams when the FSD changes — they are part of the spec, not decoration.
