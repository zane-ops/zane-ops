import { redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { userQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { deleteCookie, getCsrfTokenHeader } from "~/utils";

export async function clientAction() {
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
    throw redirect("/");
  }

  queryClient.removeQueries({
    queryKey: userQueries.authedUser.queryKey
  });
  deleteCookie("csrftoken");
  throw redirect("/login");
}

export async function clientLoader() {
  throw redirect("/");
}
