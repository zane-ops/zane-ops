import { useQuery } from "@tanstack/react-query";
import { apiClient } from "~/api/client";

export function Welcome() {
  const query = useQuery({
    queryKey: ["PING"],
    queryFn: async ({ signal }) => {
      const { data } = await apiClient.GET("/api/ping/", { signal });
      return data;
    }
  });
  return (
    <main className="flex flex-col items-center justify-center pt-16 pb-4">
      <h1 className="text-2xl">Welcome to ZaneOps</h1>
      <div>
        {query.isLoading ? (
          <span>loading...</span>
        ) : (
          <span>{query.data?.ping}</span>
        )}
      </div>
    </main>
  );
}
