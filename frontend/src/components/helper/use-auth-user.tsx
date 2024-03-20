import { useQuery } from "@tanstack/react-query";
import { apiClient } from "~/api/client";

export function useAuthUser() {
  return useQuery({
    queryKey: ["AUTHED_USER"],
    queryFn: ({ signal }) => {
      return apiClient.GET("/api/auth/me/", { signal });
    }
  });
}
