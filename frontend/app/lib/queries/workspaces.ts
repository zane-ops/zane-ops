import { keepPreviousData, queryOptions } from "@tanstack/react-query";
import { z } from "zod";
import { zfd } from "zod-form-data";
import { apiClient } from "~/api/client";
import {
  DEFAULT_QUERY_REFETCH_INTERVAL,
  WORKSPACE_ROLE_MAPPING
} from "~/lib/constants";
import { workspaceKey } from "~/lib/queries/shared";
import { notFound } from "~/lib/utils";

/************************************
 *         Workspace Queries        *
 ************************************/

export const workspaceMemberListFilters = zfd.formData({
  page: zfd.numeric().optional().catch(1).optional(),
  query: z.string().optional(),
  per_page: zfd.numeric().optional().catch(10).optional(),
  role: z
    .enum(["Viewer", "Member", "Admin", "Owner"])
    .optional()
    .catch(undefined)
});

export const paginationListFilters = zfd.formData({
  page: zfd.numeric().optional().catch(1).optional(),
  per_page: zfd.numeric().optional().catch(10).optional()
});

export const workspaceQueries = {
  members: (
    workspaceId: string,
    filters: z.infer<typeof workspaceMemberListFilters> = {}
  ) =>
    queryOptions({
      queryKey: [...workspaceKey(workspaceId), "MEMBERS", filters] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET("/api/workspace/members/", {
          signal,
          params: {
            query: {
              ...filters,
              role: filters.role
                ? WORKSPACE_ROLE_MAPPING[filters.role].value
                : undefined
            }
          }
        });
        if (!data) throw notFound("Not found");
        return data;
      },
      refetchInterval: (query) => {
        if (!query.state.data) {
          return false;
        }
        return DEFAULT_QUERY_REFETCH_INTERVAL;
      },
      placeholderData: keepPreviousData
    }),
  invitations: (
    workspaceId: string,
    filters: z.infer<typeof paginationListFilters> = {}
  ) =>
    queryOptions({
      queryKey: [...workspaceKey(workspaceId), "INVITATIONS", filters] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET("/api/workspace/invitations/", {
          signal,
          params: {
            query: filters
          }
        });
        if (!data) throw notFound("Not found");
        return data;
      },
      refetchInterval: (query) => {
        if (!query.state.data) {
          return false;
        }
        return DEFAULT_QUERY_REFETCH_INTERVAL;
      },
      placeholderData: keepPreviousData
    }),

  invitationLink: (token: string) =>
    queryOptions({
      queryKey: ["INVITATION_LINKS", token],
      queryFn: async ({ signal }) => {
        const result = await apiClient.GET(
          "/api/workspace/invitations/{token}/",
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
    }),

  member: (workspaceId: string, membershipId: string) =>
    queryOptions({
      queryKey: [
        ...workspaceKey(workspaceId),
        "MEMBERS",
        "SINGLE",
        membershipId
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/workspace/members/{membership_id}/",
          {
            signal,
            params: {
              path: {
                membership_id: membershipId
              }
            }
          }
        );
        if (!data) throw notFound("Not found");
        return data;
      },
      refetchInterval: (query) => {
        if (!query.state.data) {
          return false;
        }
        return DEFAULT_QUERY_REFETCH_INTERVAL;
      },
      placeholderData: keepPreviousData
    })
};
