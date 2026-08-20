import { JobCard } from "../../src/components/jobs/JobCard";

export function Ready() {
  return <JobCard job={{ id: "aeafcacee4c3", filename: "Kreuzungsplan.dwg", status: "ready" }} />;
}

export function Processing() {
  return (
    <JobCard job={{ id: "1e8f75db904c", filename: "Bahnuebergang_km12.dxf", status: "extracting" }} />
  );
}

export function Failed() {
  return <JobCard job={{ id: "b40ceee757b3", filename: "corrupt_plan.dwg", status: "failed" }} />;
}
