// Tiny provider-context module for design-sync previews only - the real
// app builds its own QueryClient in src/main.tsx. Referenced via
// cfg.provider's {"$ref": "queryClient"} (see .design-sync/config.json).
import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient();
