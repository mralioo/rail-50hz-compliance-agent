import { StatusBadge } from "../../src/components/jobs/StatusBadge";

export function Queued() {
  return <StatusBadge status="queued" />;
}

export function Converting() {
  return <StatusBadge status="converting" />;
}

export function Analyzing() {
  return <StatusBadge status="analyzing" />;
}

export function Ready() {
  return <StatusBadge status="ready" />;
}

export function Failed() {
  return <StatusBadge status="failed" />;
}
