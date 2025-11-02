import {
  AlertCircleIcon,
  ContainerIcon,
  GitBranchIcon,
  InfoIcon,
  LoaderIcon
} from "lucide-react";
import * as React from "react";
import { Form, href, redirect, useFetcher, useNavigation } from "react-router";
import { type RequestInput, apiClient } from "~/api/client";
import { AWSECSLogo } from "~/components/aws-ecs-logo";
import { DockerHubLogo } from "~/components/docker-hub-logo";
import { GithubLogo } from "~/components/github-logo";
import { GitlabLogo } from "~/components/gitlab-logo";
import { GoogleArtifactLogo } from "~/components/google-artifact-logo";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { SubmitButton } from "~/components/ui/button";
import {
  Command,
  CommandInput,
  CommandItem,
  CommandList
} from "~/components/ui/command";
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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { DEFAULT_REGISTRIES } from "~/lib/constants";
import {
  type ContainerRegistryCredentials,
  type Service,
  containerRegistriesQueries,
  sshKeysQueries
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

  const [selectedRegistry, setSelectedRegistry] =
    React.useState<ContainerRegistryCredentials["registry_type"]>("DOCKER_HUB");

  const [registryURL, setRegistryURL] = React.useState(
    () => DEFAULT_REGISTRIES[selectedRegistry].url
  );

  React.useEffect(() => {
    const key = Object.keys(errors ?? {})[0];
    const field = formRef.current?.elements.namedItem(key) as HTMLInputElement;
    field?.focus();
  }, [errors]);

  return (
    <fetcher.Form
      ref={formRef}
      className="flex flex-col gap-4 items-start px-2"
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
        required
        errors={errors.registry_type}
        name="registry_type"
        className="flex flex-col gap-1.5 flex-1 w-full md:w-4/5"
      >
        <FieldSetLabel htmlFor="registry_type">Registry Type</FieldSetLabel>
        <FieldSetSelect
          name="registry_type"
          value={selectedRegistry}
          defaultValue={selectedRegistry}
          onValueChange={(value) => {
            const val = value as ContainerRegistryCredentials["registry_type"];
            setSelectedRegistry(val);
            setRegistryURL(DEFAULT_REGISTRIES[val].url ?? "");
          }}
        >
          <SelectTrigger
            id="registry_type"
            ref={SelectTriggerRef}
            className={cn(
              "data-disabled:bg-secondary/60 dark:data-disabled:bg-secondary-foreground",
              "data-disabled:opacity-100 data-disabled:border-transparent"
              // healthcheckType === "none" && "text-muted-foreground"
            )}
          >
            <SelectValue placeholder="Select a type" />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(DEFAULT_REGISTRIES).map(([type, registry]) => (
              <SelectItem value={type}>
                <div className="inline-flex items-center gap-2">
                  {type === "GENERIC" && <ContainerIcon className="size-4" />}
                  {type === "DOCKER_HUB" && (
                    <DockerHubLogo className="size-4 flex-none" />
                  )}
                  {type === "GITHUB" && (
                    <GithubLogo className="size-4 flex-none" />
                  )}
                  {type === "GITLAB" && (
                    <GitlabLogo className="size-6 -mx-1 [&_path]:!fill-orange-400 flex-none" />
                  )}
                  {type === "AWS_ECR" && (
                    <AWSECSLogo className="size-4 flex-none" />
                  )}
                  {type === "GOOGLE_ARTIFACT" && (
                    <GoogleArtifactLogo className="size-4 flex-none" />
                  )}
                  <span>{registry.name}</span>
                </div>
              </SelectItem>
            ))}
          </SelectContent>
        </FieldSetSelect>
      </FieldSet>

      <FieldSet
        errors={errors.url}
        required
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
        />
      </FieldSet>
      <input type="hidden" name="url" readOnly value={registryURL} />

      <Separator className="w-full md:w-4/5 my-1" />

      <FieldSet
        errors={errors.username}
        name="username"
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
        className="w-full md:w-4/5 flex flex-col gap-1"
      >
        <FieldSetLabel className="flex items-center gap-0.5">
          Password for registry
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

  const password = formData.get("password")?.toString();
  const username = formData.get("username")?.toString();
  const userData = {
    url: formData.get("url")?.toString() ?? "",
    username: username?.trim() === "" ? undefined : username,
    password: password?.trim() === "" ? undefined : password,
    registry_type: formData
      .get("registry_type")
      ?.toString() as ContainerRegistryCredentials["registry_type"]
  } satisfies RequestInput<"post", "/api/registries/credentials/">;

  console.log({
    formData: Object.fromEntries(formData.entries()),
    userData
  });

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
  await queryClient.invalidateQueries(containerRegistriesQueries.list);
  throw redirect(href("/settings/container-registries"));
}
