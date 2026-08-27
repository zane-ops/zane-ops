import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  BrushCleaningIcon,
  CheckIcon,
  DatabaseZapIcon,
  GlobeIcon,
  LoaderIcon
} from "lucide-react";
import { useFetcher } from "react-router";
import { Code } from "~/components/code";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
import { Separator } from "~/components/ui/separator";
import { systemQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { getFormErrorsFromResponseData, metaTitle } from "~/lib/utils";
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
              <h2 className="text-lg text-grey">Http logs</h2>

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
              <h2 className="text-lg text-grey">Build Cache</h2>

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
              <h2 className="text-lg text-grey">Docker System Prune</h2>

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
  const fetcher = useFetcher();
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  return (
    <fetcher.Form method="post" className="flex flex-col gap-4">
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
  const fetcher = useFetcher();
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  return (
    <fetcher.Form method="post" className="flex flex-col gap-4">
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
  const fetcher = useFetcher();
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  return (
    <fetcher.Form method="post" className="flex flex-col gap-4">
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
          <Code className="text-xs">0 4 * * *</Code> which is every 4h.
        </p>
        <FieldSetInput
          placeholder="ex: 0 0 * * *"
          defaultValue={props.docker_system_prune_cron_schedule}
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
