import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  BrushCleaningIcon,
  CheckIcon,
  DatabaseZapIcon,
  GlobeIcon,
  LoaderIcon
} from "lucide-react";
import * as React from "react";
import { useFetcher } from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import { Code } from "~/components/code";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetCheckbox,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
import { Separator } from "~/components/ui/separator";
import { systemQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  getCsrfTokenHeader,
  getFormErrorsFromResponseData,
  metaTitle
} from "~/lib/utils";
import type { Route } from "./+types/jobs-and-schedules";

export function meta() {
  return [
    metaTitle("Jobs & Schedules")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({}: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  const settings = await queryClient.ensureQueryData(systemQueries.settings);
  return {
    settings
  };
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const formData = await request.formData();
  const body: RequestInput<"patch", "/api/console/system-settings/"> = {};

  if (formData.has("app_data_cleanup_cron_schedule")) {
    const retentionDays = formData
      .get("http_log_retention_days")
      ?.toString()
      .trim();
    body.http_log_retention_days = (retentionDays || undefined) as
      | number
      | undefined;
    body.app_data_cleanup_cron_schedule = formData
      .get("app_data_cleanup_cron_schedule")
      ?.toString();
  }

  if (formData.has("build_cache_max_age_days")) {
    const maxAge = formData.get("build_cache_max_age_days")?.toString().trim();
    const maxUsedSpace = formData
      .get("build_cache_max_use_space_bytes")
      ?.toString()
      .trim();
    body.build_cache_max_age_days = (maxAge || undefined) as number | undefined;
    body.build_cache_max_use_space_bytes = (maxUsedSpace || undefined) as
      | number
      | undefined;
  }

  if (formData.has("docker_system_prune_cron_schedule")) {
    body.docker_system_prune_cron_schedule =
      formData.get("docker_system_prune_cron_schedule")?.toString() ?? "";
    body.prune_images = formData.get("prune_images") === "on";
    body.prune_containers = formData.get("prune_containers") === "on";
    body.prune_networks = formData.get("prune_networks") === "on";
    body.prune_volumes = formData.get("prune_volumes") === "on";
  }

  const { error: errors } = await apiClient.PATCH(
    "/api/console/system-settings/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      body
    }
  );

  if (errors) {
    return { errors };
  }

  await getQueryClient().invalidateQueries({
    queryKey: systemQueries.settings.queryKey
  });

  toast.success("Success", {
    description: "Settings updated successfully",
    closeButton: true
  });

  return { errors: undefined };
}

export default function JobsAndSchedulesPage({
  loaderData
}: Route.ComponentProps) {
  const { data: settings } = useQuery({
    ...systemQueries.settings,
    initialData: loaderData.settings
  });

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-2xl">Jobs and Schedules</h2>
      <Separator />
      <h3 className="text-grey">
        Manage automated jobs settings running on this server.
      </h3>

      <div className="grid lg:grid-cols-12  relative">
        <div className="lg:col-span-10 flex flex-col">
          <section id="http-logs" className="flex gap-1 scroll-mt-20">
            <div className="w-16 hidden md:flex flex-col items-center">
              <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
                <GlobeIcon size={15} className="flex-none text-grey" />
              </div>
              <div className="h-full border border-grey/50"></div>
            </div>

            <div className="w-full flex flex-col gap-5 pt-1 pb-16">
              <div className="flex flex-col gap-1">
                <h2 className="text-lg text-grey">Http logs</h2>
                <p className="text-grey text-sm">
                  Control how long HTTP request logs are kept and when the
                  cleanup job runs.
                </p>
              </div>

              <HttplogSectionForm
                http_log_retention_days={settings.http_log_retention_days}
                app_data_cleanup_cron_schedule={
                  settings.app_data_cleanup_cron_schedule
                }
              />
            </div>
          </section>
        </div>

        <div className="lg:col-span-10 flex flex-col">
          <section id="build-cache" className="flex gap-1 scroll-mt-20">
            <div className="w-16 hidden md:flex flex-col items-center">
              <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
                <DatabaseZapIcon size={15} className="flex-none text-grey" />
              </div>
              <div className="h-full border border-grey/50"></div>
            </div>

            <div className="w-full flex flex-col gap-5 pt-1 pb-16">
              <div className="flex flex-col gap-1">
                <h2 className="text-lg text-grey">Build Cache</h2>
                <p className="text-grey text-sm">
                  Limit how much disk space and how long the image build cache
                  is retained before old layers are pruned.
                </p>
              </div>

              <BuildCacheSectionForm
                build_cache_max_age_days={settings.build_cache_max_age_days}
                build_cache_max_use_space_bytes={
                  settings.build_cache_max_use_space_bytes
                }
              />
            </div>
          </section>
        </div>

        <div className="lg:col-span-10 flex flex-col">
          <section id="docker-prune" className="flex gap-1 scroll-mt-20">
            <div className="w-16 hidden md:flex flex-col items-center">
              <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
                <BrushCleaningIcon size={15} className="flex-none text-grey" />
              </div>
            </div>

            <div className="w-full flex flex-col gap-5 pt-1 pb-8">
              <div className="flex flex-col gap-1">
                <h2 className="text-lg text-grey">Docker System Prune</h2>
                <p className="text-grey text-sm">
                  Schedule a periodic cleanup of unused Docker resources and
                  pick which ones to reclaim.
                </p>
              </div>

              <DockerSystemPruneSection {...settings} />
            </div>
          </section>
        </div>
      </div>
    </section>
  );
}

type HttplogSectionFormProps = Pick<
  Route.ComponentProps["loaderData"]["settings"],
  "http_log_retention_days" | "app_data_cleanup_cron_schedule"
>;

function HttplogSectionForm({
  http_log_retention_days,
  app_data_cleanup_cron_schedule
}: HttplogSectionFormProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);
  const formRef = React.useRef<React.ComponentRef<"form">>(null);

  React.useEffect(() => {
    const key = Object.keys(errors ?? {})[0];
    const field = formRef.current?.elements.namedItem(key) as HTMLInputElement;
    field?.focus();
  }, [errors]);

  return (
    <fetcher.Form method="post" ref={formRef} className="flex flex-col gap-4">
      {errors.non_field_errors && (
        <Alert variant="destructive">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errors.non_field_errors}</AlertDescription>
        </Alert>
      )}
      <FieldSet
        errors={errors.http_log_retention_days}
        name="http_log_retention_days"
        className="flex flex-col gap-1.5 flex-1"
      >
        <FieldSetLabel className="!text-card-foreground">
          Http Log Retention Days
        </FieldSetLabel>
        <p className="text-grey text-sm">
          An empty value means store http logs indefinitely
        </p>
        <FieldSetInput
          placeholder="<empty>"
          className="placeholder-shown:font-mono"
          defaultValue={http_log_retention_days}
        />
      </FieldSet>

      <FieldSet
        errors={errors.app_data_cleanup_cron_schedule}
        name="app_data_cleanup_cron_schedule"
        className="flex flex-col gap-1.5 flex-1"
        required
      >
        <FieldSetLabel className="!text-card-foreground">
          Cleanup CRON schedule
        </FieldSetLabel>
        <p className="text-grey text-sm">
          This schedule is also used to cleanup service metrics. <br /> Default
          value is <Code className="text-xs">0 0 * * *</Code> which is every day
          at midnight
        </p>
        <FieldSetInput
          placeholder="ex: 0 0 * * *"
          defaultValue={app_data_cleanup_cron_schedule}
        />
      </FieldSet>

      <SubmitButton
        isPending={isPending}
        variant="secondary"
        className="self-start"
      >
        {isPending ? (
          <>
            <LoaderIcon className="animate-spin" size={15} />
            <span>Updating ...</span>
          </>
        ) : (
          <>
            <CheckIcon size={15} className="flex-none" />
            <span>Update</span>
          </>
        )}
      </SubmitButton>
    </fetcher.Form>
  );
}

type BuildCacheSectionFormProps = Pick<
  Route.ComponentProps["loaderData"]["settings"],
  "build_cache_max_age_days" | "build_cache_max_use_space_bytes"
>;

function BuildCacheSectionForm({
  build_cache_max_age_days,
  build_cache_max_use_space_bytes
}: BuildCacheSectionFormProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);
  const formRef = React.useRef<React.ComponentRef<"form">>(null);

  React.useEffect(() => {
    const key = Object.keys(errors ?? {})[0];
    const field = formRef.current?.elements.namedItem(key) as HTMLInputElement;
    field?.focus();
  }, [errors]);

  return (
    <fetcher.Form method="post" ref={formRef} className="flex flex-col gap-4">
      {errors.non_field_errors && (
        <Alert variant="destructive">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errors.non_field_errors}</AlertDescription>
        </Alert>
      )}

      <FieldSet
        errors={errors.build_cache_max_age_days}
        name="build_cache_max_age_days"
        className="flex flex-col gap-1.5 flex-1"
      >
        <FieldSetLabel className="!text-card-foreground">Max Age</FieldSetLabel>
        <p className="text-grey text-sm">
          An empty value means store the build cache indefinitely
        </p>
        <FieldSetInput
          placeholder="<empty>"
          className="placeholder-shown:font-mono"
          defaultValue={build_cache_max_age_days}
        />
      </FieldSet>

      <FieldSet
        errors={errors.build_cache_max_use_space_bytes}
        name="build_cache_max_use_space_bytes"
        className="flex flex-col gap-1.5 flex-1"
      >
        <FieldSetLabel className="!text-card-foreground">
          Max Used Space (In Bytes)
        </FieldSetLabel>
        <p className="text-grey text-sm">
          Max space used by the build before cleaning up old caches.
        </p>
        <FieldSetInput
          placeholder="<empty>"
          className="placeholder-shown:font-mono"
          defaultValue={build_cache_max_use_space_bytes}
        />
      </FieldSet>

      <SubmitButton
        isPending={isPending}
        variant="secondary"
        className="self-start"
      >
        {isPending ? (
          <>
            <LoaderIcon className="animate-spin" size={15} />
            <span>Updating ...</span>
          </>
        ) : (
          <>
            <CheckIcon size={15} className="flex-none" />
            <span>Update</span>
          </>
        )}
      </SubmitButton>
    </fetcher.Form>
  );
}

type DockerSystemPruneSectionProps = Pick<
  Route.ComponentProps["loaderData"]["settings"],
  | "docker_system_prune_cron_schedule"
  | "prune_containers"
  | "prune_images"
  | "prune_networks"
  | "prune_volumes"
>;

function DockerSystemPruneSection(props: DockerSystemPruneSectionProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);
  const formRef = React.useRef<React.ComponentRef<"form">>(null);

  React.useEffect(() => {
    const key = Object.keys(errors ?? {})[0];
    const field = formRef.current?.elements.namedItem(key) as HTMLInputElement;
    field?.focus();
  }, [errors]);

  return (
    <fetcher.Form method="post" ref={formRef} className="flex flex-col gap-4">
      {errors.non_field_errors && (
        <Alert variant="destructive">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errors.non_field_errors}</AlertDescription>
        </Alert>
      )}
      <FieldSet
        errors={errors.docker_system_prune_cron_schedule}
        name="docker_system_prune_cron_schedule"
        className="flex flex-col gap-1.5 flex-1"
        required
      >
        <FieldSetLabel className="!text-card-foreground">
          Docker System Prune CRON schedule
        </FieldSetLabel>
        <p className="text-grey text-sm">
          The schedule used to cleanup images. <br /> Default value is{" "}
          <Code className="text-xs">0 */4 * * *</Code> which is every 4h.
        </p>
        <FieldSetInput
          placeholder="ex: 0 0 * * *"
          defaultValue={props.docker_system_prune_cron_schedule}
        />
      </FieldSet>

      <div className="flex flex-col gap-2 pt-3">
        <span className="text-card-foreground">Resources to prune</span>

        <FieldSet
          name="prune_images"
          errors={errors.prune_images}
          className="inline-flex gap-2 items-start"
        >
          <FieldSetCheckbox
            defaultChecked={props.prune_images}
            className="relative top-1"
          />
          <div className="flex flex-col gap-2">
            <FieldSetLabel className="!text-card-foreground">
              Images
            </FieldSetLabel>
            <p className="text-grey text-sm">
              Remove dangling and unused images to reclaim disk space.
            </p>
          </div>
        </FieldSet>

        <FieldSet
          name="prune_containers"
          errors={errors.prune_containers}
          className="inline-flex gap-2 items-start"
        >
          <FieldSetCheckbox
            defaultChecked={props.prune_containers}
            className="relative top-1"
          />
          <div className="flex flex-col gap-2">
            <FieldSetLabel className="!text-card-foreground">
              Containers
            </FieldSetLabel>
            <p className="text-grey text-sm">
              Remove stopped containers left behind by past deployments.
            </p>
          </div>
        </FieldSet>

        <FieldSet
          name="prune_networks"
          errors={errors.prune_networks}
          className="inline-flex gap-2 items-start"
        >
          <FieldSetCheckbox
            defaultChecked={props.prune_networks}
            className="relative top-1"
          />
          <div className="flex flex-col gap-2">
            <FieldSetLabel className="!text-card-foreground">
              Networks
            </FieldSetLabel>
            <p className="text-grey text-sm">
              Remove networks no longer used by any container.
            </p>
          </div>
        </FieldSet>

        <FieldSet
          name="prune_volumes"
          errors={errors.prune_volumes}
          className="inline-flex gap-2 items-start"
        >
          <FieldSetCheckbox
            defaultChecked={props.prune_volumes}
            className="relative top-1"
          />
          <div className="flex flex-col gap-2">
            <FieldSetLabel className="!text-card-foreground">
              Volumes
            </FieldSetLabel>
            <p className="text-grey text-sm">
              Remove anonymous volumes not attached to any container. This can
              delete data. Only volumes not attached to any ZaneOps service are
              deleted.
            </p>
          </div>
        </FieldSet>
      </div>

      <SubmitButton
        isPending={isPending}
        variant="secondary"
        className="self-start"
      >
        {isPending ? (
          <>
            <LoaderIcon className="animate-spin" size={15} />
            <span>Updating ...</span>
          </>
        ) : (
          <>
            <CheckIcon size={15} className="flex-none" />
            <span>Update</span>
          </>
        )}
      </SubmitButton>
    </fetcher.Form>
  );
}
