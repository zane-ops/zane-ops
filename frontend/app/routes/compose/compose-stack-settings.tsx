import { useQuery } from "@tanstack/react-query";
import {
  CableIcon,
  ContainerIcon,
  FileSlidersIcon,
  FlameIcon,
  GitBranchIcon,
  HammerIcon,
  HardDriveDownloadIcon,
  HardDriveIcon,
  InfoIcon,
  KeyRoundIcon,
  ScrollTextIcon
} from "lucide-react";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import {
  composeStackQueries,
  environmentQueries,
  resourceQueries,
  serviceQueries
} from "~/lib/queries";
import { queryClient } from "~/root";
import { ComposeStackSlugForm } from "~/routes/compose/components/compose-stack-slug-form";
import { ServiceAutoDeployForm } from "~/routes/services/components/service-auto-deploy-form";
import { ServiceBuilderForm } from "~/routes/services/components/service-builder-form";
import { ServiceCommandForm } from "~/routes/services/components/service-command-form";
import { ServiceConfigsForm } from "~/routes/services/components/service-configs-form";
import { ServiceDangerZoneForm } from "~/routes/services/components/service-danger-zone-form";
import {
  ServiceDeployURLForm,
  ServicePreviewDeployURLForm
} from "~/routes/services/components/service-deploy-url-form";
import { ServiceGitSourceForm } from "~/routes/services/components/service-git-source-form";
import { ServiceHealthcheckForm } from "~/routes/services/components/service-healthcheck-form";
import { ServicePortsForm } from "~/routes/services/components/service-ports-form";
import { ServiceResourceLimits } from "~/routes/services/components/service-resource-limits-form";
import { ServiceSharedVolumesForm } from "~/routes/services/components/service-shared-volumes-form";
import { ServiceSlugForm } from "~/routes/services/components/service-slug-form";
import { ServiceSourceForm } from "~/routes/services/components/service-source-form";
import { ServiceURLsForm } from "~/routes/services/components/service-urls-form";
import { ServiceVolumesForm } from "~/routes/services/components/service-volumes-form";
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
    <div className="mt-8">
      <div className="lg:col-span-10 flex flex-col max-w-full">
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

        <section id="configs" className="flex gap-1 scroll-mt-24 max-w-full">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <ScrollTextIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>
          <div className="w-full flex flex-col gap-5 pt-1 pb-14">
            <h2 className="text-lg text-grey">User content</h2>
            {/* <ServiceConfigsForm
              project_slug={project_slug}
              service_slug={service_slug}
              env_slug={env_slug}
            /> */}
          </div>
        </section>

        <section id="networking" className="flex gap-1 scroll-mt-24">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <KeyRoundIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>
          <div className="w-full flex flex-col gap-12 pt-1 pb-14">
            <div className="flex flex-col gap-6">
              <h2 className="text-lg text-grey">Environment overrides</h2>

              {/* <ServicePortsForm
              service_slug={service_slug}
              project_slug={project_slug}
              env_slug={env_slug}
            /> */}
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

            {/* <ServiceDeployURLForm
              project_slug={project_slug}
              service_slug={service_slug}
              env_slug={env_slug}
            /> */}
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
            {/* <ServiceDangerZoneForm
              project_slug={project_slug}
              service_slug={service_slug}
              env_slug={env_slug}
            /> */}
          </div>
        </section>
      </div>
    </div>
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
