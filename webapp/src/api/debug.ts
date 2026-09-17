import { apiGet } from "./client";

export interface LiveSessionStatus {
  job_id: string;
  display: string;
  pid: number;
  process_alive: boolean;
  uptime_s: number;
  op_port: number;
  op_port_open: boolean;
  html_port: number;
  html_ready: boolean;
  html_url: string;
}

export interface RequestLogEntry {
  ts: string;
  method: string;
  path: string;
  status: number;
  duration_ms: number;
}

export interface CommandLogEntry {
  ts: string;
  job_id: string;
  transport: "headless" | "live";
  op: string;
  ok: boolean;
  detail: string;
}

export function getDebugSession(): Promise<{ session: LiveSessionStatus | null }> {
  return apiGet<{ session: LiveSessionStatus | null }>("/debug/session");
}

export function getDebugRequests(): Promise<RequestLogEntry[]> {
  return apiGet<RequestLogEntry[]>("/debug/requests");
}

export function getDebugCommands(): Promise<CommandLogEntry[]> {
  return apiGet<CommandLogEntry[]>("/debug/commands");
}

export function getDebugXpraLog(lines = 200): Promise<{ path: string; lines: string[] }> {
  return apiGet<{ path: string; lines: string[] }>(`/debug/xpra-log?lines=${lines}`);
}
