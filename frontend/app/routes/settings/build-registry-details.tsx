import { Separator } from "~/components/ui/separator";
import {
  type BuildRegistry,
  type RegistryStorageBackend,
  buildRegistryQueries
} from "~/lib/queries";
import { queryClient } from "~/root";
import { getCsrfTokenHeader, metaTitle } from "~/utils";
import type { Route } from "./+types/build-registry-details";

import { useQuery } from "@tanstack/react-query";
import { AlertCircleIcon, FolderIcon, LoaderIcon } from "lucide-react";
import * as React from "react";
import {
  href,
  redirect,
  useFetcher,
  useLoaderData,
  useParams
} from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import { AWSECSLogo } from "~/components/aws-ecs-logo";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetCheckbox,
  FieldSetInput,
  FieldSetLabel,
  FieldSetPasswordToggleInput,
  FieldSetSelect
} from "~/components/ui/fieldset";
import {
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "~/components/ui/select";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";

export function meta() {
  return [
    metaTitle("Build Registry details")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const registry = await queryClient.ensureQueryData(
    buildRegistryQueries.single(params.id)
  );
  return {
    registry
  };
}

export default function EditBuildRegistryPage({
  loaderData
}: Route.ComponentProps) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Edit Build Registry</h2>
      </div>
      <Separator />
      <EditBuildRegistryForm />
    </div>
  );
}

function EditBuildRegistryForm() {
  const fetcher = useFetcher<typeof clientAction>();
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const SelectTriggerRef =
    React.useRef<React.ComponentRef<typeof SelectTrigger>>(null);

  const params = useParams();
  const loaderData = useLoaderData<typeof clientLoader>();

  const { data: registry } = useQuery({
    ...buildRegistryQueries.single(params.id!),
    initialData: loaderData.registry
  });

  const [storageBackend, setStorageBackend] = React.useState<
    BuildRegistry["storage_backend"]
  >(registry.storage_backend);

  React.useEffect(() => {
    const key = Object.keys(errors ?? {})[0];
    if (key === "storage_backend") {
      SelectTriggerRef.current?.focus();
      return;
    }

    const field = formRef.current?.querySelector(
      `[name="${key}"]`
    ) as HTMLInputElement | null;
    field?.focus();
  }, [errors]);

  return (
    <fetcher.Form
      method="post"
      ref={formRef}
      className="flex flex-col gap-4 items-start"
    >
      {errors.non_field_errors && (
        <Alert variant="destructive" className="w-full md:w-4/5">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errors.non_field_errors}</AlertDescription>
        </Alert>
      )}
      <FieldSet
        errors={errors.name}
        name="name"
        required
        className="w-full md:w-4/5 flex flex-col gap-1"
      >
        <FieldSetLabel className="flex items-center gap-0.5">
          Name
        </FieldSetLabel>

        <FieldSetInput
          defaultValue={registry.name}
          autoFocus
          placeholder="ex: production-registry"
        />
      </FieldSet>

      <FieldSet
        errors={errors.registry_domain}
        name="registry_domain"
        required
        className="w-full md:w-4/5 flex flex-col gap-1"
      >
        <FieldSetLabel className="flex items-center gap-0.5">
          Domain
        </FieldSetLabel>

        <FieldSetInput
          defaultValue={registry.registry_domain}
          placeholder="registry.mysupersaas.com"
        />
      </FieldSet>

      <FieldSet
        name="is_default"
        errors={errors.is_default}
        className="flex-1 inline-flex gap-2 flex-col"
      >
        <div className="inline-flex gap-2 items-start">
          <FieldSetCheckbox
            defaultChecked={registry.is_default}
            className="relative top-1"
          />

          <div className="flex flex-col gap-0.5">
            <FieldSetLabel className="inline-flex gap-1 items-center dark:text-card-foreground">
              Set as default
            </FieldSetLabel>

            <small className="text-grey text-sm">
              Use this registry to store all built application images. This will
              replace any existing default.
            </small>
          </div>
        </div>
      </FieldSet>

      <FieldSet
        name="is_secure"
        errors={errors.is_secure}
        className="flex-1 inline-flex gap-2 flex-col"
      >
        <div className="inline-flex gap-2 items-start">
          <FieldSetCheckbox
            defaultChecked={registry.is_secure}
            className="relative top-1"
          />

          <div className="flex flex-col gap-0.5">
            <FieldSetLabel className="inline-flex gap-1 items-center dark:text-card-foreground">
              Use HTTPS
            </FieldSetLabel>

            <small className="text-grey text-sm">
              Connect to this registry using HTTPS (recommended)
            </small>
          </div>
        </div>
      </FieldSet>

      <Separator />

      <div className="flex flex-col gap-4 w-full">
        <h3 className="text-lg">Authentication</h3>

        <FieldSet
          errors={errors.registry_username}
          name="registry_username"
          required
          className="w-full md:w-4/5 flex flex-col gap-1"
        >
          <FieldSetLabel>Username</FieldSetLabel>

          <FieldSetInput
            defaultValue={registry.registry_username}
            placeholder="ex: zane"
          />
        </FieldSet>

        <FieldSet
          errors={errors.registry_password}
          name="registry_password"
          className="w-full md:w-4/5 flex flex-col gap-1"
        >
          <FieldSetLabel className="flex items-center gap-2">
            Password
            <span className="text-grey dark:text-card-foreground">
              (Only fill if you need to update)
            </span>
          </FieldSetLabel>

          <FieldSetPasswordToggleInput />
        </FieldSet>
      </div>

      <Separator />

      <div className="flex flex-col gap-4 w-full">
        <h3 className="text-lg">Storage Configuration</h3>

        <FieldSet
          errors={errors.storage_backend}
          name="storage_backend"
          className="flex flex-col gap-1.5 flex-1 w-full md:w-4/5"
        >
          <FieldSetLabel htmlFor="storage_backend">
            Storage Backend
          </FieldSetLabel>
          <FieldSetSelect
            name="storage_backend"
            value={storageBackend}
            onValueChange={(value) => {
              const val = value as RegistryStorageBackend;
              setStorageBackend(val);
            }}
          >
            <SelectTrigger
              id="storage_backend"
              ref={SelectTriggerRef}
              className={cn(
                "data-disabled:bg-secondary/60 dark:data-disabled:bg-secondary-foreground",
                "data-disabled:opacity-100 data-disabled:border-transparent",
                "[&_[data-description]]:hidden [&_[data-description]]:md:block [&_[data-item]]:flex-row [&_[data-item]]:gap-2"
              )}
            >
              <SelectValue placeholder="Select a storage backend" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem
                value="LOCAL"
                className="flex items-start [&_[data-indicator]]:relative [&_[data-indicator]]:top-1"
              >
                <div className="inline-flex items-start gap-2">
                  <FolderIcon className="size-4 flex-none relative top-1" />
                  <div className="flex flex-col" data-item>
                    <span>Local Filesystem</span>
                    <span className="text-muted-foreground" data-description>
                      Store container images on the ZaneOps server
                    </span>
                  </div>
                </div>
              </SelectItem>
              <SelectItem
                value="S3"
                className="flex items-start [&_[data-indicator]]:relative [&_[data-indicator]]:top-1"
              >
                <div className="inline-flex items-start gap-2">
                  <AWSECSLogo className="flex-none size-3 relative top-1" />
                  <div className="flex flex-col" data-item>
                    <span>S3-Compatible Storage</span>
                    <span className="text-muted-foreground" data-description>
                      Store images in AWS S3 or compatible services (R2, MinIO,
                      etc.)
                    </span>
                  </div>
                </div>
              </SelectItem>
            </SelectContent>
          </FieldSetSelect>
        </FieldSet>

        {storageBackend === "S3" && (
          <>
            {errors.s3_credentials?.non_field_errors && (
              <Alert variant="destructive" className="w-full md:w-4/5">
                <AlertCircleIcon className="h-4 w-4" />
                <AlertTitle>Error</AlertTitle>
                <AlertDescription>
                  {errors.s3_credentials.non_field_errors}
                </AlertDescription>
              </Alert>
            )}

            <FieldSet
              errors={errors.s3_credentials?.bucket}
              name="s3_credentials.bucket"
              required
              className="w-full md:w-4/5 flex flex-col gap-1"
            >
              <FieldSetLabel className="flex items-center gap-0.5">
                S3 Bucket Name
              </FieldSetLabel>

              <FieldSetInput
                defaultValue={registry.s3_credentials.bucket}
                placeholder="ex: my-registry-images"
              />
            </FieldSet>

            <FieldSet
              errors={errors.s3_credentials?.access_key}
              name="s3_credentials.access_key"
              required
              className="w-full md:w-4/5 flex flex-col gap-1"
            >
              <FieldSetLabel className="flex items-center gap-0.5">
                Access Key ID
              </FieldSetLabel>

              <FieldSetInput
                defaultValue={registry.s3_credentials.access_key}
                placeholder="ex: akiaiosfodnn7example"
              />
            </FieldSet>

            <FieldSet
              errors={errors.s3_credentials?.secret_key}
              required
              name="s3_credentials.secret_key"
              className="w-full md:w-4/5 flex flex-col gap-1"
            >
              <FieldSetLabel className="flex items-center gap-2">
                Secret Access Key
                <span className="text-grey dark:text-card-foreground">
                  (Only fill if you need to update)
                </span>
              </FieldSetLabel>

              <FieldSetPasswordToggleInput />
            </FieldSet>
            <FieldSet
              errors={errors.s3_credentials?.region}
              name="s3_credentials.region"
              className="w-full md:w-4/5 flex flex-col gap-1"
            >
              <FieldSetLabel className="flex items-center gap-2">
                S3 Region
              </FieldSetLabel>

              <FieldSetInput
                defaultValue={registry.s3_credentials.region}
                placeholder="ex: us-east-1"
              />
            </FieldSet>
            <FieldSet
              errors={errors.s3_credentials?.endpoint}
              name="s3_credentials.endpoint"
              className="w-full md:w-4/5 flex flex-col gap-1"
            >
              <FieldSetLabel className="flex items-center gap-2">
                Custom Endpoint URL
                <span className="text-card-foreground">
                  (leave empty for AWS S3)
                </span>
              </FieldSetLabel>

              <FieldSetInput
                defaultValue={registry.s3_credentials.endpoint}
                placeholder="ex: https://s3.us-west-1.myhost.com"
              />
            </FieldSet>

            <FieldSet
              errors={errors.s3_credentials?.secure}
              name="s3_credentials.secure"
              className="flex-1 inline-flex gap-2 flex-col"
            >
              <div className="inline-flex gap-2 items-start">
                <FieldSetCheckbox
                  defaultChecked={registry.s3_credentials.secure}
                  className="relative top-1"
                />

                <div className="flex flex-col gap-0.5">
                  <FieldSetLabel className="inline-flex gap-1 items-center dark:text-card-foreground">
                    Use HTTPS for S3 endpoint
                  </FieldSetLabel>

                  <small className="text-grey text-sm">
                    Connect to the S3 endpoint using HTTPS (recommended)
                  </small>
                </div>
              </div>
            </FieldSet>
          </>
        )}
      </div>

      <SubmitButton
        isPending={fetcher.state !== "idle"}
        className="mt-4"
        name="intent"
        value="update"
      >
        {fetcher.state !== "idle" ? (
          <>
            <LoaderIcon className="animate-spin" size={15} />
            <span>Updating registry...</span>
          </>
        ) : (
          "Update Registry"
        )}
      </SubmitButton>
    </fetcher.Form>
  );
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const formData = await request.formData();

  const storage_backend = formData
    .get("storage_backend")
    ?.toString() as RegistryStorageBackend;
  const password = formData.get("registry_password")?.toString();
  const userData: RequestInput<
    "patch",
    "/api/registries/build-registries/{id}/"
  > = {
    name: formData.get("name")?.toString() ?? "",
    registry_domain: formData.get("registry_domain")?.toString() ?? "",
    registry_username: formData.get("registry_username")?.toString() ?? "",
    registry_password: password ? password : undefined,
    storage_backend: storage_backend,
    is_secure: formData.get("is_secure") === "on",
    is_default: formData.get("is_default") === "on"
  };

  if (storage_backend === "S3") {
    const s3_endpoint = formData.get("s3_credentials.endpoint")?.toString();
    const s3_region = formData.get("s3_credentials.region")?.toString();
    const s3_secret_key = formData.get("s3_credentials.secret_key")?.toString();

    userData["s3_credentials"] = {
      bucket: formData.get("s3_credentials.bucket")?.toString() ?? "",
      access_key: formData.get("s3_credentials.access_key")?.toString() ?? "",
      secret_key: s3_secret_key ? s3_secret_key : undefined,
      secure: formData.get("s3_credentials.secure")?.toString() === "on",
      endpoint: s3_endpoint ? s3_endpoint : undefined,
      region: s3_region ? s3_region : undefined
    };
  }
  const { error: errors } = await apiClient.PATCH(
    "/api/registries/build-registries/{id}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: params
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

  toast.success("Success", {
    dismissible: true,
    closeButton: true,
    description: "Build Registry updated succesfully"
  });
  await queryClient.invalidateQueries({
    predicate(query) {
      const key = buildRegistryQueries.list({}).queryKey[0];
      return query.queryKey.includes(key);
    }
  });
  throw redirect(href("/settings/build-registries"));
}
