import { useQuery } from "@tanstack/react-query";
import { getDebugSession, getDebugRequests, getDebugCommands, getDebugXpraLog } from "../api/debug";

const POLL_MS = 2000;

export function useDebugSession() {
  return useQuery({
    queryKey: ["debug", "session"],
    queryFn: getDebugSession,
    refetchInterval: POLL_MS,
  });
}

export function useDebugRequests() {
  return useQuery({
    queryKey: ["debug", "requests"],
    queryFn: getDebugRequests,
    refetchInterval: POLL_MS,
  });
}

export function useDebugCommands() {
  return useQuery({
    queryKey: ["debug", "commands"],
    queryFn: getDebugCommands,
    refetchInterval: POLL_MS,
  });
}

export function useDebugXpraLog(enabled: boolean) {
  return useQuery({
    queryKey: ["debug", "xpra-log"],
    queryFn: () => getDebugXpraLog(200),
    refetchInterval: enabled ? POLL_MS : false,
    enabled,
  });
}
