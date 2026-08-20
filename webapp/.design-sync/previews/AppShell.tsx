import { AppShell } from "../../src/components/layout/AppShell";

export function WithPageContent() {
  return (
    <div style={{ height: 640 }}>
      <AppShell>
        <div style={{ padding: "2.5rem 1.5rem", maxWidth: 768, margin: "0 auto" }}>
          <h1 style={{ fontSize: "1.25rem", fontWeight: 600, color: "#dfe4ea" }}>Dashboard</h1>
          <p style={{ marginTop: 8, fontSize: "0.875rem", color: "#8a92a1" }}>
            Recent plans and job status live here — this is example page content composed
            inside the shell to show layout, not a real route.
          </p>
        </div>
      </AppShell>
    </div>
  );
}
