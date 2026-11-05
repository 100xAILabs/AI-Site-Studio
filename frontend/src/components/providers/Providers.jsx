"use client";

/**
 * Client-side providers wrapper.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export default function Providers({ children }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 1000 * 60 * 5, // 5 minutes cache validity
            gcTime: 1000 * 60 * 30, // 30 minutes in memory
            retry: 1,
            refetchOnWindowFocus: false,
            refetchOnMount: false, // Instant zero-flicker transitions
            refetchOnReconnect: false,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}
