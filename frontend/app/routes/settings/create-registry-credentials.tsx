import { AlertCircleIcon, LoaderIcon } from "lucide-react";
import * as React from "react";
import { href, redirect, useFetcher } from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
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
import { Separator } from "~/components/ui/separator";
import { DEFAULT_REGISTRIES } from "~/lib/constants";
import {
  type ContainerRegistryType,
  containerRegistriesQueries
} from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import { queryClient } from "~/root";
import { getCsrfTokenHeader, metaTitle } from "~/utils";
import type { Route } from "./+types/create-registry-credentials";

export function meta() {
  return [
    metaTitle("New Registry Credentials")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export default function NameOfComponentPage() {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Add New Registry Credentials</h2>
      </div>
      <Separator />
      <CreateRegistryCredentialsForm />
    </div>
  );
}

function CreateRegistryCredentialsForm() {
  const fetcher = useFetcher<typeof clientAction>();
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const isPending = fetcher.state !== "idle";
  const SelectTriggerRef =
    React.useRef<React.ComponentRef<typeof SelectTrigger>>(null);

  const [selectedRegistryType, setSelectedRegistryType] =
    React.useState<ContainerRegistryType>("DOCKER_HUB");

  const [registryURL, setRegistryURL] = React.useState(
    () => DEFAULT_REGISTRIES[selectedRegistryType].url
  );

  React.useEffect(() => {
    const key = Object.keys(errors ?? {})[0];
    if (key === "registry_type") {
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
      ref={formRef}
      className="flex flex-col gap-4 items-start"
      method="POST"
    >
      {errors.non_field_errors && (
        <Alert variant="destructive">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errors.non_field_errors}</AlertDescription>
        </Alert>
      )}

      <FieldSet
        errors={errors.slug}
        name="slug"
        required
        className="w-full md:w-4/5 flex flex-col gap-1"
      >
        <FieldSetLabel className="flex items-center gap-0.5">
          Slug
        </FieldSetLabel>

        <FieldSetInput autoFocus placeholder="ex: docker-hub" />
      </FieldSet>

      <FieldSet
        required
        errors={errors.registry_type}
        name="registry_type"
        className="flex flex-col gap-1.5 flex-1 w-full md:w-4/5"
      >
        <FieldSetLabel htmlFor="registry_type">Registry Type</FieldSetLabel>
        <FieldSetSelect
          name="registry_type"
          value={selectedRegistryType}
          defaultValue={selectedRegistryType}
          onValueChange={(value) => {
            const val = value as ContainerRegistryType;
            setSelectedRegistryType(val);
            setRegistryURL(DEFAULT_REGISTRIES[val].url ?? "");
          }}
        >
          <SelectTrigger
            id="registry_type"
            ref={SelectTriggerRef}
            className={cn(
              "data-disabled:bg-secondary/60 dark:data-disabled:bg-secondary-foreground",
              "data-disabled:opacity-100 data-disabled:border-transparent"
            )}
          >
            <SelectValue placeholder="Select a type" />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(DEFAULT_REGISTRIES).map(([type, registry]) => {
              const Icon =
                DEFAULT_REGISTRIES[type as ContainerRegistryType].Icon;
              return (
                <SelectItem value={type}>
                  <div className="inline-flex items-center gap-2">
                    <Icon />
                    <span>{registry.name}</span>
                  </div>
                </SelectItem>
              );
            })}
          </SelectContent>
        </FieldSetSelect>
      </FieldSet>

      <FieldSet
        errors={errors.url}
        required
        name="url"
        className="w-full md:w-4/5 flex flex-col gap-1"
      >
        <FieldSetLabel className="flex items-center gap-0.5">
          Registry URL
        </FieldSetLabel>
        <FieldSetInput
          value={registryURL}
          disabled={DEFAULT_REGISTRIES[selectedRegistryType].isUrlFixed}
          onChange={(ev) => setRegistryURL(ev.currentTarget.value)}
          placeholder="ex: https://registry.hub.docker.com"
          className="disabled:opacity-100"
        />
      </FieldSet>
      <input type="hidden" name="url" readOnly value={registryURL} />

      <Separator className="w-full md:w-4/5 my-1" />

      <FieldSet
        errors={errors.username}
        name="username"
        required
        className="w-full md:w-4/5 flex flex-col gap-1"
      >
        <FieldSetLabel className="flex items-center gap-0.5">
          Username for registry
        </FieldSetLabel>
        <FieldSetInput placeholder="ex: centipede123" />
      </FieldSet>

      <FieldSet
        errors={errors.password}
        name="password"
        required
        className="w-full md:w-4/5 flex flex-col gap-1"
      >
        <FieldSetLabel className="flex items-center gap-0.5">
          {selectedRegistryType !== "GENERIC" ? "Token" : "Password"} for
          registry
        </FieldSetLabel>
        <FieldSetPasswordToggleInput />
      </FieldSet>

      <SubmitButton isPending={isPending}>
        {isPending ? (
          <>
            Adding Credentials...{" "}
            <LoaderIcon size={15} className="animate-spin" />
          </>
        ) : (
          <>Add Credentials</>
        )}
      </SubmitButton>
    </fetcher.Form>
  );
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const formData = await request.formData();

  const userData = {
    url: formData.get("url")?.toString() ?? "",
    slug: formData.get("slug")?.toString() ?? "",
    username: formData.get("username")?.toString() ?? "",
    password: formData.get("password")?.toString() ?? "",
    registry_type: formData
      .get("registry_type")
      ?.toString() as ContainerRegistryType
  } satisfies RequestInput<"post", "/api/registries/credentials/">;

  const { error: errors } = await apiClient.POST(
    "/api/registries/credentials/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
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
    description: "Container Registry Credentials created succesfully"
  });
  await queryClient.invalidateQueries(containerRegistriesQueries.list);
  throw redirect(href("/settings/shared-credentials"));
}
