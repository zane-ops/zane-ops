import { useQuery } from "@tanstack/react-query";
import { apiClient } from "~/api/client";

export function useProjectList() {
  return useQuery({
    queryKey: ["PROJECT_LIST"],
    queryFn: ({ signal }) => {
      return apiClient.GET("/api/projects/", { signal });
    }
  });
}

export function useProjectStatus(id: string) {
  return useQuery({
    queryKey: [id],
    queryFn: ({ signal }) => {
      return apiClient.GET(`/api/projects/status-list?ids=${id}`, { signal });
    }
  });
}
