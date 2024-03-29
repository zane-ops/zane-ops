import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createLazyFileRoute, useNavigate } from "@tanstack/react-router";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import { useAuthUser } from "~/components/helper/use-auth-user";
import { userKeys } from "~/key-factories";
import { apiClient } from "../api/client";
import { deleteCookie, getCookie } from "../utils";

export const Route = createLazyFileRoute("/")({
  component: withAuthRedirect(AuthedView)
});

function AuthedView() {
  const navigate = useNavigate();
  const query = useAuthUser();
  const user = query.data?.data?.user;

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
        queryKey: userKeys.authedUser
      });
      deleteCookie("csrftoken");
      navigate({ to: "/login" });
      return null;
    }
  });

  if (!user) {
    return null;
  }

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
