import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createLazyFileRoute, useNavigate } from "@tanstack/react-router";
import { ApiResponse, apiClient } from "../api/client";
import { deleteCookie, getCookie } from "../utils";
import { withAuthRedirect } from "~/components/helper/auth-redirect";

export const Route = createLazyFileRoute("/")({
  component: withAuthRedirect(AuthedView)
});

function AuthedView({ user }: ApiResponse<"get", "/api/auth/me/">) {
  const queryClient = useQueryClient();
  const { data, isPending, mutate } = useMutation({
    mutationFn: async () => {
      // set csrf cookie token
      await apiClient.GET("/api/csrf/");
      const csrfToken = getCookie("csrftoken");
      const { error } = await apiClient.DELETE("/api/auth/logout/", {
        headers: {
          "X-CSRFToken": csrfToken
        }
      });
      if (error) {
        return error;
      }

      queryClient.removeQueries({
        queryKey: ["AUTHED_USER"]
      });
      deleteCookie("csrftoken");
    }
  });
  return (
    <dl>
      <h1>
        Welcome, <span style={{ color: "dodgerblue" }}>{user.username}</span>
      </h1>

      <form action={() => mutate()}>
        <button disabled={isPending}>
          {isPending ? "Logging out..." : "Logout"}
        </button>

        {data?.detail && <div style={{ color: "red" }}>{data.detail}</div>}
      </form>
    </dl>
  );
}
