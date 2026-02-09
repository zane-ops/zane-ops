import { useQuery } from "@tanstack/react-query";
import {
  FileTextIcon,
  FlameIcon,
  HammerIcon,
  InfoIcon,
  KeyRoundIcon,
  ScrollTextIcon
} from "lucide-react";
import { Link } from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import {
  composeStackQueries,
  environmentQueries,
  resourceQueries
} from "~/lib/queries";
import { queryClient } from "~/root";
import { ComposeStackDangerZoneForm } from "~/routes/compose/components/compose-stack-danger-zone-form";
import { ComposeStackDeployURLForm } from "~/routes/compose/components/compose-stack-deploy-url-form";
import { ComposeStackEnvForm } from "~/routes/compose/components/compose-stack-env-form";
import { ComposeStackSlugForm } from "~/routes/compose/components/compose-stack-slug-form";
import { ComposeStackUserContentForm } from "~/routes/compose/components/compose-stack-user-content-form";
import { getCsrfTokenHeader } from "~/utils";
import type { Route } from "./+types/compose-stack-settings";

export default function ComposeStackSettingsPage({
  params,
  matches: {
    2: { loaderData }
  }
}: Route.ComponentProps) {
  const { data: stack } = useQuery({
    ...composeStackQueries.single({
      project_slug: params.projectSlug,
      stack_slug: params.composeStackSlug,
      env_slug: params.envSlug
    }),
    initialData: loaderData.stack
  });

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 relative mt-8 max-w-full">
      <div className="flex flex-col w-full max-w-full lg:col-span-10">
        <section id="details" className="flex gap-1 scroll-mt-24">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <InfoIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>

          <div className="w-full flex flex-col gap-5 pt-1 pb-8">
            <h2 className="text-lg text-grey">Details</h2>
            <ComposeStackSlugForm
              stack_slug={params.composeStackSlug}
              project_slug={params.projectSlug}
              env_slug={params.envSlug}
            />
          </div>
        </section>

        <section
          id="compose-file"
          className="flex gap-1 scroll-mt-24 max-w-full"
        >
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <FileTextIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>
          <div className="w-full flex flex-col gap-5 pt-1 pb-14">
            <h2 className="text-lg text-grey">Compose file</h2>
            <ComposeStackUserContentForm stack={stack} />
          </div>
        </section>

        <section id="env-overrides" className="flex gap-1 scroll-mt-24">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <KeyRoundIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>
          <div className="w-full flex flex-col gap-12 pt-1 pb-14">
            <div className="flex flex-col gap-6">
              <h2 className="text-lg text-grey">Environment overrides</h2>

              <ComposeStackEnvForm stack={stack} />
            </div>
          </div>
        </section>

        <section id="deploy" className="flex gap-1 scroll-mt-24">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <HammerIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>
          <div className="w-full flex flex-col gap-12 pt-1 pb-14">
            <h2 className="text-lg text-grey">Deploy</h2>

            <ComposeStackDeployURLForm stack={stack} />
          </div>
        </section>

        <section id="danger" className="flex gap-1 scroll-mt-24">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-red-500">
              <FlameIcon size={15} className="flex-none text-red-500" />
            </div>
          </div>
          <div className="w-full flex flex-col gap-5 pt-1 pb-14">
            <h2 className="text-lg text-red-400">Danger Zone</h2>
            <ComposeStackDangerZoneForm
              projectSlug={params.projectSlug}
              envSlug={params.envSlug}
              stackSlug={params.composeStackSlug}
            />
          </div>
        </section>
      </div>

      <StackSettingsSideNav />
    </div>
  );
}

function StackSettingsSideNav() {
  return (
    <aside className="col-span-2 hidden lg:flex flex-col h-full">
      <nav className="sticky top-20 flex flex-col gap-4">
        <ul className="flex flex-col gap-2 text-grey">
          <li>
            <Link
              to={{
                hash: "#main"
              }}
            >
              Details
            </Link>
          </li>
          <li>
            <Link
              to={{
                hash: "#compose-file"
              }}
            >
              Compose file
            </Link>
          </li>
          <li>
            <Link
              to={{
                hash: "#env-overrides"
              }}
            >
              Environment overrides
            </Link>
          </li>
          <li>
            <Link
              to={{
                hash: "#deploy"
              }}
            >
              Deploy
            </Link>
          </li>

          <li className="text-red-400">
            <Link
              to={{
                hash: "#danger"
              }}
            >
              Danger Zone
            </Link>
          </li>
        </ul>
      </nav>
    </aside>
  );
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const formData = await request.formData();
  const intent = formData.get("intent")?.toString();

  switch (intent) {
    case "update-slug": {
      return updateStackSlug({
        project_slug: params.projectSlug,
        stack_slug: params.composeStackSlug,
        env_slug: params.envSlug,
        formData
      });
    }
    case "request-stack-change": {
      return requestStackChange({
        project_slug: params.projectSlug,
        stack_slug: params.composeStackSlug,
        env_slug: params.envSlug,
        formData
      });
    }
    default: {
      throw new Error(`Unexpected intent \`${intent}\``);
    }
  }
}

async function updateStackSlug({
  project_slug,
  stack_slug,
  env_slug,
  formData
}: {
  project_slug: string;
  stack_slug: string;
  env_slug: string;
  formData: FormData;
}) {
  const userData = {
    slug: formData.get("slug")?.toString()
  } satisfies RequestInput<
    "put",
    "/api/compose/stacks/{project_slug}/{env_slug}/{slug}/"
  >;

  await queryClient.cancelQueries({
    queryKey: composeStackQueries.single({ project_slug, stack_slug, env_slug })
      .queryKey,
    exact: true
  });

  const { error: errors, data } = await apiClient.PUT(
    "/api/compose/stacks/{project_slug}/{env_slug}/{slug}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug,
          slug: stack_slug,
          env_slug
        }
      },
      body: userData
    }
  );

  if (errors) {
    return {
      errors,
      userData
    };
  }

  await Promise.all([
    queryClient.invalidateQueries(
      composeStackQueries.single({
        project_slug,
        stack_slug,
        env_slug
      })
    ),
    queryClient.invalidateQueries(
      environmentQueries.composeStackList(project_slug, env_slug)
    ),
    queryClient.invalidateQueries({
      predicate: (query) =>
        query.queryKey[0] === resourceQueries.search().queryKey[0]
    })
  ]);

  toast.success("Success", {
    description: "Compose Stack updated succesfully",
    closeButton: true
  });
  if (data.slug !== stack_slug) {
    queryClient.setQueryData(
      composeStackQueries.single({
        project_slug,
        stack_slug: data.slug,
        env_slug
      }).queryKey,
      data
    );
  }
  return {
    data
  };
}

type ChangeRequestBody = RequestInput<
  "put",
  "/api/compose/stacks/{project_slug}/{env_slug}/{slug}/request-changes/"
>;
type FindByType<Union, Type> = Union extends { field: Type } ? Union : never;
type BodyOf<Type extends ChangeRequestBody["field"]> = FindByType<
  ChangeRequestBody,
  Type
>;

async function requestStackChange({
  project_slug,
  stack_slug,
  env_slug,
  formData
}: {
  project_slug: string;
  stack_slug: string;
  env_slug: string;
  formData: FormData;
}) {
  const field = formData
    .get("change_field")
    ?.toString() as ChangeRequestBody["field"];
  const type = formData
    .get("change_type")
    ?.toString() as ChangeRequestBody["type"];
  const item_id = formData.get("item_id")?.toString();

  let userData = null;
  switch (field) {
    case "env_overrides": {
      userData = {
        key: formData.get("key")?.toString() ?? "",
        value: formData.get("value")?.toString() ?? ""
      } satisfies BodyOf<typeof field>["new_value"];
      break;
    }
    case "compose_content": {
      const content = formData.get("user_content")?.toString().trim() ?? "";
      userData = content satisfies BodyOf<typeof field>["new_value"];
      break;
    }

    default: {
      throw new Error(`Unexpected field \`${field}\``);
    }
  }

  let toastId: string | number | undefined;
  if (type === "DELETE") {
    toastId = toast.loading("Sending change request...");
    userData = undefined;
  }
  const { error: errors, data } = await apiClient.PUT(
    "/api/compose/stacks/{project_slug}/{env_slug}/{slug}/request-changes/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug,
          slug: stack_slug,
          env_slug
        }
      },
      body: {
        field,
        type,
        new_value: userData,
        item_id
      } as BodyOf<typeof field>
    }
  );
  if (errors) {
    if (toastId) {
      const fullErrorMessage = errors.errors.map((err) => err.detail).join(" ");

      toast.error("Failed to send change request", {
        description: fullErrorMessage,
        id: toastId,
        closeButton: true
      });
    }
    return {
      errors,
      userData
    };
  }

  await queryClient.invalidateQueries({
    ...composeStackQueries.single({
      project_slug,
      stack_slug,
      env_slug
    }),
    exact: true
  });

  if (toastId) {
    toast.success("Change request sent", { id: toastId, closeButton: true });
  }

  return {
    data: { ...data, slug: stack_slug }
  };
}
