> ## ⚠️ SUPERSEDED TWICE — Azure Edition (2026-05-19)
> This document remains the **vision and "why"** for MediSync. The tech-stack table in §2 below has been **superseded twice**:
>
> **First amendment (2026-05-17, AWS serverless):**
> - EKS/Fargate → AWS Lambda; RDS → DynamoDB; AppSync/IoT Core → deferred; gRPC → dropped (events only); Analytics → deferred; SMS → dropped (SES email only).
>
> **Second amendment (2026-05-19, Azure pivot after AWS suspension):**
> - Lambda → **Azure Functions** (Python v2 model)
> - DynamoDB → **Cosmos DB for NoSQL (serverless)**
> - EventBridge/SNS → **Event Grid**
> - Step Functions → **Durable Functions**
> - Cognito → **Entra External ID**
> - X-Ray → **Application Insights / OpenTelemetry**
> - SES → **Azure Communication Services — Email**
> - IAM roles → **Entra ID + RBAC + Managed Identities**
>
> **`context.md` is the authoritative tech reference.** Use this file for the storytelling (problem, solution, business value) and §3 "Brilliant Features" (Terraform, distributed tracing, Chaos Engineering, CI/CD) — those *concepts* still apply; only the vendor names changed. The AWS service names in §2 below are kept for reading-history continuity only.
>
> ---

To build a "brilliant" portfolio project, you need to move beyond standard CRUD apps (like a simple e-commerce site or a To-Do list). You need a project that demonstrates **event-driven architecture, scalability, and data processing.**

Here is a project idea that is timely, socially impactful, and technically challenging:

---

### Project Title: **"MediSync: A Decentralized Emergency Blood & Organ Supply Chain"**

#### The Problem:
In many developing regions (and even some developed ones), there is a massive information gap between blood banks, hospitals, and donors. People often post desperate pleas on Twitter/X or WhatsApp for rare blood types or urgent supplies. There is no real-time, microservice-based system that connects inventory levels with live emergency demand.

#### The Solution:
A microservices-based platform that tracks blood/organ inventory in real-time, uses geo-fencing to alert nearby donors, and provides an emergency "Handshake" protocol between hospitals for supply transfers.

---

### 1. The Microservices Architecture
To make this a true microservice project, you should split the logic into at least 4-5 independent services:

1.  **User/Donor Service:** Manages profiles, blood types, and medical history (encrypted).
2.  **Inventory Service:** Tracks units of blood/organs available at specific hospital IDs.
3.  **Matching & Notification Service:** The "Brain." It listens for "Emergency Requests" and finds the nearest donor or hospital with stock.
4.  **Logistics/Tracking Service:** Tracks the transit of the supply from point A to point B using real-time GPS.
5.  **Analytics Service:** Aggregates data to predict which regions will have a shortage next month (AI/ML integration).

---

### 2. The AWS Tech Stack (The "How")
This stack shows recruiters you know how to use the **AWS Well-Architected Framework**:

*   **Compute:** **AWS EKS (Kubernetes)** or **AWS ECS with Fargate**. This shows you can manage containers.
*   **API Gateway:** Use **Amazon API Gateway** as the single entry point for your frontend/mobile app.
*   **Communication (The most important part):** 
    *   *Asynchronous:* Use **Amazon SNS/SQS** or **Amazon EventBridge** for communication between services (e.g., when inventory drops, trigger the Notification service).
    *   *Synchronous:* Use **gRPC** for internal service-to-service communication to show you understand high-performance networking.
*   **Database:** 
    *   **Amazon DynamoDB:** For Donor profiles and real-time inventory (High speed).
    *   **Amazon RDS (PostgreSQL):** For complex relational data like hospital hierarchies and audit logs.
*   **Storage:** **Amazon S3** for storing medical reports or donor ID photos.
*   **Real-time:** **AWS AppSync (GraphQL)** or **AWS IoT Core** for real-time tracking of blood transport vehicles on a map.
*   **Security:** **AWS Cognito** for user authentication and **AWS Secrets Manager** for database credentials.

---

### 3. "Brilliant" Features to make it Portfolio-Ready
To make a recruiter say "Wow," add these advanced engineering components:

*   **Infrastructure as Code (IaC):** Do not build this in the AWS Console. Use **Terraform** or **AWS CDK**. This is a non-negotiable skill for high-paying roles.
*   **Observability:** Implement **AWS X-Ray** for distributed tracing. Show a screenshot in your GitHub readme of how a request travels through 3 different microservices.
*   **Chaos Engineering:** Mention how you used **AWS Fault Injection Simulator** to test what happens if the "Inventory Service" goes down (Does the rest of the app stay alive?).
*   **CI/CD Pipeline:** Set up **GitHub Actions** to automatically deploy to AWS every time you push code.

---

### 4. Why this solves a "People Problem"
1.  **Reduces Waste:** Blood has an expiration date. Your analytics service can predict where blood is needed before it expires.
2.  **Saves Lives:** Reduces the "Time-to-Donor" from hours of social media searching to minutes of automated matching.
3.  **Transparency:** Provides a clear audit trail of where a donation went, increasing public trust.

---

### How to present this in your Portfolio:
*   **The "Why":** "I built MediSync because 20% of emergency deaths in [Region] are due to delayed blood supply."
*   **The Architecture Diagram:** Use Lucitchart or Eraser.io to create a clean AWS diagram.
*   **The "Challenge" section:** "I struggled with data consistency between the Inventory and Matching services, so I implemented the **Saga Pattern** to handle distributed transactions." (This sentence alone will get you interviews).

**Would you like me to dive deeper into the database schema or the Terraform setup for one of these services?**