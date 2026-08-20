import { JobStatusStepper } from "../../src/components/jobs/JobStatusStepper";

export function Queued() {
  return <JobStatusStepper status="queued" />;
}

export function Converting() {
  return <JobStatusStepper status="converting" />;
}

export function Extracting() {
  return <JobStatusStepper status="extracting" />;
}

export function Analyzing() {
  return <JobStatusStepper status="analyzing" />;
}
