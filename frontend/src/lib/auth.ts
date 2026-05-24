import type { Role } from "./types";

// TODO(entra): replace this stub with MSAL.js + Entra External ID sign-in
// once the Entra External ID tenant exists (context.md §3, §8). Until then
// the UI runs as a fixed demo operator so the rest of the app can be built
// and demoed.

export interface DemoUser {
  name: string;
  role: Role;
}

export const currentUser: DemoUser = {
  name: "Demo Operator",
  role: "Hospital",
};
