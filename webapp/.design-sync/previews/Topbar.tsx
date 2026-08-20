import { Topbar } from "../../src/components/layout/Topbar";

export function Ready() {
  return <Topbar filename="Kreuzungsplan.dwg" status="ready" />;
}

export function Analyzing() {
  return <Topbar filename="Kreuzungsplan.dwg" status="analyzing" />;
}

export function Failed() {
  return <Topbar filename="Kreuzungsplan.dwg" status="failed" />;
}
