import { href, redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { passwordTokenQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { getCsrfTokenHeader } from "~/lib/utils";
import type { Route } from "./+types/password-link-details";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  throw redirect(href("/admin/password-links"));
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const formData = await request.formData();
  const intent = formData.get("intent")?.toString();

  switch (intent) {
    case "delete_password_token": {
      return deletePasswordToken(params.tokenId);
    }
    default: {
      throw new Error("Unexpected intent");
    }
  }
}

async function deletePasswordToken(tokenId: string) {
  const queryClient = getQueryClient();

  const { error: errors } = await apiClient.DELETE(
    "/api/console/password-tokens/{id}",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: { id: tokenId }
      }
    }
  );

  if (errors) {
    const fullErrorMessage = errors.errors
      .map((err) => (err.attr ? `${err.attr}: ` : "") + err.detail)
      .join(" ");

    toast.error("Could not delete the password reset link", {
      description: fullErrorMessage,
      closeButton: true
    });
    return { errors };
  }

  await queryClient.invalidateQueries({
    queryKey: passwordTokenQueries.list().queryKey.slice(0, 1)
  });

  toast.success("Password reset link deleted", {
    closeButton: true,
    description: <span>The link can no longer be used to set a password.</span>
  });

  return { data: null };
}
