import { error } from "console";
import type path from "path";
import { useQuery } from "@tanstack/react-query";
import { AlertCircleIcon, ExternalLinkIcon, LoaderIcon } from "lucide-react";
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
import type { Route } from "./+types/container-registry-credentials-details";

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const credentials = await queryClient.ensureQueryData(
    containerRegistriesQueries.single(params.id)
  );

  return {
    credentials
  };
}

export default function ContainerRegistryCredentialDetailsPage() {
  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Edit Registry Credentials</h2>
      </div>
      <Separator />

      <EditRegistryCredentialsForm />
    </section>
  );
}

function EditRegistryCredentialsForm() {
  const fetcher = useFetcher<typeof clientAction>();
  const params = useParams<Route.ComponentProps["params"]>();
  const loaderData = useLoaderData<typeof clientLoader>();

  const { data: credentials } = useQuery({
    ...containerRegistriesQueries.single(params.id!),
    initialData: loaderData.credentials
  });

  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const isPending = fetcher.state !== "idle";
  const SelectTriggerRef =
    React.useRef<React.ComponentRef<typeof SelectTrigger>>(null);

  const [selectedRegistry, setSelectedRegistry] =
    React.useState<ContainerRegistryType>(credentials.registry_type);

  const [registryURL, setRegistryURL] = React.useState(credentials.url);

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
        <Alert variant="destructive" className="md:w-4/5">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errors.non_field_errors}</AlertDescription>
        </Alert>
      )}

      <FieldSet
        required
        className="flex flex-col gap-1.5 flex-1 w-full md:w-4/5"
      >
        <FieldSetLabel htmlFor="registry_type">Registry Type</FieldSetLabel>
        <FieldSetSelect
          name="registry_type"
          disabled
          value={selectedRegistry}
          defaultValue={selectedRegistry}
          onValueChange={(value) => {
            const val = value as ContainerRegistryType;
            setSelectedRegistry(val);
            setRegistryURL(DEFAULT_REGISTRIES[val].url ?? "");
          }}
        >
          <SelectTrigger
            className={cn(
              "disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
              "disabled:border-transparent disabled:opacity-100"
            )}
            id="registry_type"
            ref={SelectTriggerRef}
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
          autoFocus
          value={registryURL}
          disabled={DEFAULT_REGISTRIES[selectedRegistry].isUrlFixed}
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
        required={selectedRegistry !== "GENERIC"}
        className="w-full md:w-4/5 flex flex-col gap-1"
      >
        <FieldSetLabel className="flex items-center gap-0.5">
          Username for registry
        </FieldSetLabel>
        <FieldSetInput
          placeholder="ex: centipede123"
          defaultValue={credentials.username}
        />
      </FieldSet>

      <FieldSet
        errors={errors.password}
        name="password"
        required={selectedRegistry !== "GENERIC"}
        className="w-full md:w-4/5 flex flex-col gap-1"
      >
        <FieldSetLabel className="flex items-center gap-0.5">
          Password for registry
        </FieldSetLabel>
        <FieldSetPasswordToggleInput defaultValue={credentials.password} />
      </FieldSet>

      <input type="hidden" name="intent" value="update" />

      <SubmitButton isPending={isPending}>
        {isPending ? (
          <>
            <span>Updating Credentials...</span>
            <LoaderIcon size={15} className="animate-spin" />
          </>
        ) : (
          <>Update Credentials</>
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

  const intent = formData.get("intent");

  console.log({
    intent,
    data: Object.fromEntries(formData.entries())
  });

  switch (intent) {
    case "update":
      return updateCredentials(params.id, formData);
    case "delete":
      return deleteCredentials(params.id, formData);
    case "test":
      return testCredentials(params.id, formData);
    default:
      throw new Error(`invalid intent ${intent}`);
  }
}

async function deleteCredentials(id: string, formData: FormData) {
  const userData = {
    username: formData.get("username")?.toString() ?? "",
    url: formData.get("url")?.toString() ?? ""
  };
  const { error } = await apiClient.DELETE(
    "/api/registries/credentials/{id}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: { id: id }
      }
    }
  );

  if (error) {
    const fullErrorMessage = error.errors.map((err) => err.detail).join(" ");
    toast.error("Error", {
      description: fullErrorMessage,
      closeButton: true
    });
    throw redirect(href("/settings/container-registries"));
  }
  toast.success("Success", {
    description: (
      <span>
        Successfully removed Credentials for&nbsp;
        {userData.username && (
          <>
            <span className="text-link">{userData.username}</span>
            &nbsp;at&nbsp;
          </>
        )}
        <span className="text-link">{userData.url}</span>
        &nbsp;
      </span>
    ),
    closeButton: true
  });

  return { data: { success: true }, errors: undefined };
}

async function testCredentials(id: string, formData: FormData) {
  const userData = {
    username: formData.get("username")?.toString() ?? "",
    url: formData.get("url")?.toString() ?? ""
  };
  const { error, data } = await apiClient.GET(
    "/api/registries/credentials/{id}/test/",
    {
      params: {
        path: { id: id }
      }
    }
  );

  if (error) {
    const fullErrorMessage = error.errors.map((err) => err.detail).join(" ");
    toast.error("Error", {
      description: fullErrorMessage,
      closeButton: true
    });

    throw redirect(href("/settings/container-registries"));
  }
  await queryClient.invalidateQueries(containerRegistriesQueries.list);
  toast.success("Success", {
    description: (
      <span>
        Credentials for&nbsp;
        {userData.username && (
          <>
            <span className="text-link">{userData.username}</span>
            &nbsp;at&nbsp;
          </>
        )}
        <span className="text-link">{userData.url}</span>
        &nbsp; are valid
      </span>
    ),
    closeButton: true
  });
  return { data, errors: undefined };
}

async function updateCredentials(id: string, formData: FormData) {
  const password = formData.get("password")?.toString();
  const username = formData.get("username")?.toString();
  const userData = {
    url: formData.get("url")?.toString() ?? "",
    username: username?.trim() === "" ? undefined : username,
    password: password?.trim() === "" ? undefined : password
  } satisfies RequestInput<"put", "/api/registries/credentials/{id}/">;

  const { error: errors } = await apiClient.PUT(
    "/api/registries/credentials/{id}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      body: userData,
      params: {
        path: { id: id }
      }
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
    description: "Container Registry Credentials updated succesfully"
  });
  await queryClient.invalidateQueries(containerRegistriesQueries.list);
  throw redirect(href("/settings/container-registries"));
}
