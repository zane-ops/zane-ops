import { href, redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { userQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { deleteCookie, getCsrfTokenHeader, wait } from "~/utils";

export async function clientAction() {
  const queryClient = getQueryClient();
  const { error } = await apiClient.DELETE("/api/auth/logout/", {
    headers: {
      ...(await getCsrfTokenHeader())
    }
  });
  if (error) {
    const fullErrorMessage = error.errors.map((err) => err.detail).join(" ");

    toast.error("Error", {
      description: fullErrorMessage,
      closeButton: true
    });
    throw redirect(href("/"));
  }

  queryClient.removeQueries({
    queryKey: userQueries.authedUser.queryKey
  });
  deleteCookie("csrftoken");
  throw redirect(href("/login"));
}

export async function clientLoader() {
  throw redirect(href("/"));
}
