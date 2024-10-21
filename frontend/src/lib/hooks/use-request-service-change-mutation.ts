import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type RequestInput, apiClient } from "~/api/client";
import { serviceKeys } from "~/key-factories";
import { getCsrfTokenHeader } from "~/utils";

type ChangeRequestBody = RequestInput<
  "put",
  "/api/projects/{project_slug}/request-service-changes/docker/{service_slug}/"
>;
type FindByType<Union, Type> = Union extends { field: Type } ? Union : never;
type BodyOf<Type extends ChangeRequestBody["field"]> = FindByType<
  ChangeRequestBody,
  Type
>;

type useRequestServiceChangeMutationArgs<TField> = {
  project_slug: string;
  service_slug: string;
  field: TField;
  onSuccess?: () => void;
};

export function useRequestServiceChangeMutation<
  TField extends ChangeRequestBody["field"]
>({
  project_slug,
  service_slug,
  field,
  onSuccess
}: useRequestServiceChangeMutationArgs<TField>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: Omit<BodyOf<TField>, "field">) => {
      const { error, data } = await apiClient.PUT(
        "/api/projects/{project_slug}/request-service-changes/docker/{service_slug}/",
        {
          headers: {
            ...(await getCsrfTokenHeader())
          },
          params: {
            path: {
              project_slug,
              service_slug
            }
          },
          body: { ...input, field } as BodyOf<TField>
        }
      );
      if (error) {
        return error;
      }

      if (data) {
        await queryClient.invalidateQueries({
          queryKey: serviceKeys.single(project_slug, service_slug, "docker"),
          exact: true
        });
        onSuccess?.();
        return;
      }
    }
  });
}
