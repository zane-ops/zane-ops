import { useQuery } from "@tanstack/react-query";
import { apiClient } from "~/api/client";

const THIRTY_MINUTES = 30 * 60 * 1000; // in milliseconds

export function useAuthUser() {
  return useQuery({
    queryKey: ["AUTHED_USER"],
    queryFn: ({ signal }) => {
      return apiClient.GET("/api/auth/me/", { signal });
    },
    refetchInterval: (query) => {
      if (query.state.data?.data?.user) {
        return THIRTY_MINUTES;
      }
      return false;
    }
  });
}
