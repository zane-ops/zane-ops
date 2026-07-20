import { href, redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { deleteCookie, getCsrfTokenHeader } from "~/lib/utils";

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
    throw redirect(href("/"));
  }

  deleteCookie("csrftoken");
  window.location.href = href("/login");
}

export async function clientLoader() {
  throw redirect(href("/"));
}
