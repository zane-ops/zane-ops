import { queryOptions } from "@tanstack/react-query";
import { apiClient } from "~/api/client";
import { DEFAULT_QUERY_REFETCH_INTERVAL } from "~/lib/constants";
import { notFound } from "~/lib/utils";

export const sshKeysQueries = {
  list: queryOptions({
    queryKey: ["SSH_KEYS"] as const,
    queryFn: async ({ signal }) => {
      const { data } = await apiClient.GET("/api/shell/ssh-keys/", {
        signal
      });
      if (!data) {
        throw notFound("Oops !");
      }
      return data;
    },
    refetchInterval: (query) => {
      if (query.state.data) {
        return DEFAULT_QUERY_REFETCH_INTERVAL;
      }
      return false;
    }
  })
};
