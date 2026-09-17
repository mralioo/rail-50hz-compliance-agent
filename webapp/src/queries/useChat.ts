import { useMutation } from "@tanstack/react-query";
import { sendChat } from "../api/chat";

export function useChat(jobId: string | undefined) {
  return useMutation({
    mutationFn: (message: string) => sendChat(jobId as string, message),
  });
}
