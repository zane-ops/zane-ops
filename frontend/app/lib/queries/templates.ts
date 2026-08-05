import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";
import { zfd } from "zod-form-data";
import type {
  TemplateDetailsApiResponse,
  TemplateSearchAPIResponse
} from "~/api/types";
import { TEMPLATE_API_HOST } from "~/lib/constants";
import { notFound } from "~/lib/utils";

/************************************
 *       Stack Template Queries     *
 ************************************/

export const templateSearchFilters = zfd.formData({
  query: z.string().optional().catch(""),
  page: zfd.numeric().catch(1).optional().default(1),
  perPage: zfd.numeric().optional().catch(15).optional().default(15),
  tags: zfd.repeatable(z.array(z.string())).optional().default([])
});

export type TemplateSearchFilters = z.infer<typeof templateSearchFilters>;

export const templateQueries = {
  search: (filters: TemplateSearchFilters) =>
    queryOptions({
      queryKey: ["TEMPLATE_SEARCH", filters],
      queryFn: async ({ signal }) => {
        const url = new URL("/api/search", TEMPLATE_API_HOST);

        if (filters.query) {
          url.searchParams.set("q", filters.query);
        }

        if (filters.page) {
          url.searchParams.set("page", filters.page.toString());
        }

        if (filters.perPage) {
          url.searchParams.set("per_page", filters.perPage.toString());
        }

        for (const tag of filters.tags) {
          url.searchParams.append("tags", tag);
        }

        const response = await fetch(url, { signal });

        if (!response.ok) {
          throw new Error("Failed to fetch templates");
        }

        return response.json() as Promise<TemplateSearchAPIResponse>;
      }
    }),
  tags: queryOptions({
    queryKey: ["TEMPLATE_SEARCH", "TAGS"],
    queryFn: async ({ signal }) => {
      const url = new URL("/api/tags.json", TEMPLATE_API_HOST);
      const response = await fetch(url, { signal });

      if (!response.ok) {
        throw new Error("Failed to fetch tags");
      }

      return response.json() as Promise<string[]>;
    }
  }),
  single: (templateSlug: string) =>
    queryOptions({
      queryKey: ["TEMPLATE_SEARCH", templateSlug],
      queryFn: async ({ signal }) => {
        const url = new URL(
          `/api/templates/${templateSlug}.json`,
          TEMPLATE_API_HOST
        );
        const response = await fetch(url, { signal });

        if (!response.ok) {
          throw notFound("This template doesn't exist on ZaneOps");
        }

        return response.json() as Promise<TemplateDetailsApiResponse>;
      }
    })
};
