import { type QueryClient, queryOptions } from "@tanstack/react-query";
import { href, redirect } from "react-router";
import { apiClient } from "~/api/client";
import { durationToMs, hasMinRole, notFound } from "~/lib/utils";

export const userQueries = {
  authedUser: queryOptions({
    queryKey: ["AUTHED_USER"] as const,
    queryFn: async ({ signal }) => {
      const { data } = await apiClient.GET("/api/auth/me/", { signal });
      return data ?? null;
    },
    refetchInterval: (query) => {
      if (query.state.data) {
        return durationToMs(30, "minutes");
      }
      return false;
    }
  }),

  memberships: queryOptions({
    queryKey: ["WORKSPACE_MEMBERSHIP", "LIST"] as const,
    queryFn: async ({ signal }) => {
      const { data } = await apiClient.GET("/api/workspaces/list/", { signal });
      return data ?? null;
    },
    refetchInterval: (query) => {
      if (query.state.data) {
        return durationToMs(30, "minutes");
      }
      return false;
    }
  }),

  checkUserExistence: queryOptions({
    queryKey: ["CHECK_USER_EXISTENCE"] as const,
    queryFn: async ({ signal }) => {
      const result = await apiClient.GET("/api/auth/check-user-existence/", {
        signal
      });

      // if rate limited, throw error
      if (result.response.status === 429) {
        const fullErrorMessage = result.error?.errors
          .map((err) => err.detail)
          .join(" ");

        throw new Error(fullErrorMessage);
      }

      return result;
    }
  }),

  passwordResetToken: (token: string) =>
    queryOptions({
      queryKey: ["PASSWORD_RESET_TOKEN", token] as const,
      queryFn: async ({ signal }) => {
        const result = await apiClient.GET(
          "/api/auth/reset-password/{token}/",
          {
            signal,
            params: {
              path: { token }
            }
          }
        );

        // if rate limited, throw error
        if (result.response.status === 429) {
          const fullErrorMessage = result.error?.errors
            .map((err) => err.detail)
            .join(" ");

          throw new Error(fullErrorMessage);
        }

        if (!result.data) {
          const fullErrorMessage = result.error?.errors
            .map((err) => err.detail)
            .join(" ");

          throw notFound(fullErrorMessage);
        }

        return result.data;
      }
    })
};

/**
 * Fetches the authed user and redirects to `/login` if there isn't one.
 * Centralizes the "what if there isn't one" case instead of leaving it to
 * each `clientLoader` to null-check and redirect on its own.
 */
export async function ensureAuthedUser(queryClient: QueryClient) {
  const user = await queryClient.ensureQueryData(userQueries.authedUser);
  if (!user) {
    throw redirect(href("/login"));
  }
  return user;
}

/**
 * Fetches the authed user and throws a 404 if they don't have at least
 * `roleName` in the current workspace. Centralizes the auth + role check
 * instead of leaving it to each `clientLoader` to do both on its own.
 */
export async function ensureMinRole(
  queryClient: QueryClient,
  roleName: Parameters<typeof hasMinRole>[1]
) {
  const user = await ensureAuthedUser(queryClient);
  if (!hasMinRole(user, roleName)) {
    throw notFound(
      import.meta.env.DEV
        ? "You do have permission to view this page"
        : "Not found"
    );
  }
  return user;
}
