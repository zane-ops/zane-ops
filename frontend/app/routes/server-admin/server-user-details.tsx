import { href, redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { serverUserQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { type ErrorResponseFromAPI, getCsrfTokenHeader } from "~/lib/utils";
import type { Route } from "./+types/server-user-details";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  throw redirect(href("/admin/users"));
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const formData = await request.formData();
  const intent = formData.get("intent")?.toString();

  switch (intent) {
    case "toggle_user_active": {
      return toggleUserActive(params.userId, formData);
    }
    case "delete_user": {
      return deleteUser(params.userId, formData);
    }
    default: {
      throw new Error("Unexpected intent");
    }
  }
}

async function toggleUserActive(userId: string, formData: FormData) {
  const queryClient = getQueryClient();
  const is_active = formData.get("is_active")?.toString() === "on";

  const { data, error: errors } = await apiClient.PATCH(
    "/api/console/users/{id}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: { id: userId }
      },
      body: { is_active }
    }
  );

  if (errors) {
    const fullErrorMessage = errors.errors
      .map((err) => (err.attr ? `${err.attr}: ` : "") + err.detail)
      .join(" ");

    toast.error("Error", {
      description: fullErrorMessage,
      closeButton: true
    });
    return { errors };
  }

  await queryClient.invalidateQueries({
    queryKey: serverUserQueries.list().queryKey.slice(0, 1)
  });

  toast.success("Success", {
    closeButton: true,
    description: (
      <span>
        User <strong>{data.username}</strong> has been{" "}
        {is_active ? "enabled" : "disabled"}.
      </span>
    )
  });

  return { data };
}

async function deleteUser(userId: string, formData: FormData) {
  const queryClient = getQueryClient();

  const { data: user, error: notFoundError } = await apiClient.GET(
    "/api/console/users/{id}/",
    {
      params: {
        path: { id: userId }
      }
    }
  );

  if (notFoundError) {
    return { errors: notFoundError };
  }

  if (formData.get("username")?.toString().trim() !== user.username) {
    return {
      errors: {
        type: "validation_error",
        errors: [
          {
            attr: "username",
            code: "invalid",
            detail: "The username does not match"
          }
        ]
      } satisfies ErrorResponseFromAPI
    };
  }

  const { error: errors } = await apiClient.DELETE("/api/console/users/{id}/", {
    headers: {
      ...(await getCsrfTokenHeader())
    },
    params: {
      path: { id: userId }
    }
  });

  if (errors) {
    return { errors };
  }

  await queryClient.invalidateQueries({
    queryKey: serverUserQueries.list().queryKey.slice(0, 1)
  });

  toast.success("Success", {
    closeButton: true,
    description: (
      <span>
        User <strong>{user.username}</strong> has been deleted.
      </span>
    )
  });

  return { data: null };
}
