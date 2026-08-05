import { keepPreviousData, queryOptions } from "@tanstack/react-query";
import { z } from "zod";
import { zfd } from "zod-form-data";
import { apiClient } from "~/api/client";
import { DEFAULT_QUERY_REFETCH_INTERVAL } from "~/lib/constants";
import { workspaceKey } from "~/lib/queries/shared";
import { notFound } from "~/lib/utils";

export const projectSearchSchema = zfd.formData({
  slug: z.string().optional().catch(undefined),
  sort_by: zfd
    .repeatable(z.array(z.enum(["slug", "-updated_at"])))
    .optional()
    .catch(undefined)
});

export type ProjectSearch = z.infer<typeof projectSearchSchema>;
export const projectQueries = {
  list: ({
    workspaceId,
    filters = {},
    refetchInterval = DEFAULT_QUERY_REFETCH_INTERVAL
  }: {
    workspaceId: string;
    filters?: ProjectSearch;
    refetchInterval?: number;
  }) =>
    queryOptions({
      queryKey: [
        ...workspaceKey(workspaceId),
        "PROJECT_LIST",
        filters
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET("/api/projects/", {
          params: {
            query: {
              ...filters
            }
          },
          signal
        });
        if (!data) {
          throw notFound(`Not found`);
        }
        return data;
      },
      placeholderData: keepPreviousData,
      refetchInterval: (query) => {
        if (query.state.data) {
          return refetchInterval;
        }
        return false;
      }
    }),
  single: (workspaceId: string, slug: string) =>
    queryOptions({
      queryKey: [...workspaceKey(workspaceId), "PROJECT_SINGLE", slug] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET("/api/projects/{slug}/", {
          params: {
            path: {
              slug
            }
          },
          signal
        });
        if (!data) {
          throw notFound(
            `The project \`${slug}\` does not exist on this workspace`
          );
        }
        return data;
      },
      placeholderData: keepPreviousData
    })
};

/**
 * Preview templates are part of a project
 */
export const previewTemplatesQueries = {
  list: (workspaceId: string, project_slug: string) =>
    queryOptions({
      queryKey: [
        ...projectQueries.single(workspaceId, project_slug).queryKey,
        "PREVIEW_TEMPLATES"
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/projects/{slug}/preview-templates/",
          {
            signal,
            params: {
              path: {
                slug: project_slug
              }
            }
          }
        );
        if (!data) {
          throw notFound("Oops !");
        }
        return data;
      },
      refetchInterval: (query) => {
        if (query.state.data) {
          return DEFAULT_QUERY_REFETCH_INTERVAL;
        }
        return false;
      }
    }),
  single: (workspaceId: string, project_slug: string, template_slug: string) =>
    queryOptions({
      queryKey: [
        ...previewTemplatesQueries.list(workspaceId, project_slug).queryKey,
        template_slug
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/projects/{project_slug}/preview-templates/{template_slug}/",
          {
            signal,
            params: {
              path: {
                project_slug,
                template_slug
              }
            }
          }
        );
        if (!data) {
          throw notFound("This preview template does not exist !");
        }
        return data;
      },
      refetchInterval: (query) => {
        if (query.state.data) {
          return DEFAULT_QUERY_REFETCH_INTERVAL;
        }
        return false;
      }
    })
};
