import { queryOptions } from "@tanstack/react-query";
import { apiClient } from "~/api/client";
import { DEFAULT_QUERY_REFETCH_INTERVAL } from "~/lib/constants";
import { projectQueries } from "~/lib/queries/projects";
import { notFound } from "~/lib/utils";

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
