import {
  AlertCircleIcon,
  CheckIcon,
  ChevronRightIcon,
  ExternalLinkIcon,
  EyeIcon,
  EyeOffIcon,
  GitPullRequestArrowIcon,
  GithubIcon,
  GitlabIcon,
  LoaderIcon,
  LockKeyholeIcon,
  PlusIcon,
  Trash2Icon,
  WebhookIcon
} from "lucide-react";
import * as React from "react";
import {
  href,
  redirect,
  useFetcher,
  useNavigate,
  useParams
} from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { CopyButton } from "~/components/copy-button";

import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "~/components/ui/dialog";
import {
  FieldSet,
  FieldSetCheckbox,
  FieldSetInput,
  FieldSetLabel,
  FieldSetSelect
} from "~/components/ui/fieldset";
import {
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "~/components/ui/select";

import { StatusBadge } from "~/components/status-badge";
import { Separator } from "~/components/ui/separator";

import { env } from "process";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
import { Input } from "~/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import {
  type Project,
  environmentQueries,
  projectQueries,
  resourceQueries
} from "~/lib/queries";
import {
  type ErrorResponseFromAPI,
  cn,
  getFormErrorsFromResponseData,
  isNotFoundError
} from "~/lib/utils";
import { queryClient } from "~/root";
import { getCsrfTokenHeader, metaTitle } from "~/utils";
import type { Route } from "./+types/project-environments";

export function meta({ error, params }: Route.MetaArgs) {
  const title = !error
    ? `\`${params.projectSlug}\` environments`
    : isNotFoundError(error)
      ? "Error 404 - Project does not exist"
      : "Oops";
  return [metaTitle(title)] satisfies ReturnType<Route.MetaFunction>;
}

export default function ProjectEnvironmentsPage({
  matches: {
    "2": {
      data: { project }
    }
  }
}: Route.ComponentProps) {
  return (
    <section className="flex gap-1 scroll-mt-20">
      <div className="w-full flex flex-col gap-4 pb-14">
        <div className="flex  items-center gap-4">
          <h2 className="text-2xl">Environments</h2>
          <CreateEnvironmentFormDialog environments={project.environments} />
        </div>
        <Separator />

        <p className="text-grey">
          Each environment provides a separate instance of each service.&nbsp;
          <a
            href="https://zaneops.dev/knowledge-base/environments/"
            target="_blank"
            className="text-link underline inline-flex gap-1 items-center"
          >
            Read the docs <ExternalLinkIcon size={12} />
          </a>
        </p>
        <EnvironmentList environments={project.environments} />
      </div>
    </section>
  );
}

type EnvironmentListProps = {
  environments: Project["environments"];
};
function EnvironmentList({ environments }: EnvironmentListProps) {
  return (
    <div className="grid lg:grid-cols-12 gap-4 w-full">
      {environments.map((env, index) => (
        <React.Fragment key={env.id}>
          {index > 0 && (
            <hr className="border lg:col-span-10 border-dashed border-border" />
          )}
          <section className="flex flex-col gap-2 lg:col-span-10">
            <EnvironmentItem environment={env} />
          </section>
        </React.Fragment>
      ))}
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
    case "rename_environment": {
      return renameEnvironment(params.projectSlug, formData);
    }
    case "create_environment": {
      const clone_from = formData.get("clone_from")?.toString();
      if (clone_from) {
        return cloneEnvironment(params.projectSlug, clone_from, formData);
      }
      return createEnvironment(params.projectSlug, formData);
    }
    case "archive_environment": {
      if (
        formData.get("name")?.toString().trim() !==
        `${params.projectSlug}/${formData.get("environment")?.toString()}`
      ) {
        return {
          errors: {
            type: "validation_error",
            errors: [
              {
                attr: "name",
                code: "invalid",
                detail: "The environment name does not match"
              }
            ]
          } satisfies ErrorResponseFromAPI
        };
      }
      return archiveEnvironment(
        params.projectSlug,
        formData.get("environment")!.toString()
      );
    }
    default: {
      throw new Error("Unexpected intent");
    }
  }
}

async function renameEnvironment(project_slug: string, formData: FormData) {
  const userData = {
    name: formData.get("name")?.toString() ?? ""
  };
  const currentEnvironment = formData.get("current_environment")?.toString()!;

  const { error, data } = await apiClient.PATCH(
    "/api/projects/{slug}/environment-details/{env_slug}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          slug: project_slug,
          env_slug: currentEnvironment
        }
      },
      body: userData
    }
  );

  if (error) {
    return {
      userData,
      errors: error
    };
  }

  toast.success("Environment renamed successfully!", { closeButton: true });

  if (data.name !== currentEnvironment) {
    await Promise.all([
      queryClient.invalidateQueries(projectQueries.single(project_slug)),
      queryClient.invalidateQueries(
        environmentQueries.serviceList(project_slug, currentEnvironment)
      )
    ]);
  }
  return { data };
}

async function createEnvironment(project_slug: string, formData: FormData) {
  const userData = {
    name: formData.get("name")?.toString() ?? ""
  };

  const { error, data } = await apiClient.POST(
    "/api/projects/{slug}/create-environment/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          slug: project_slug
        }
      },
      body: userData
    }
  );

  if (error) {
    return {
      userData,
      errors: error
    };
  }

  toast.success(`Environment "${userData.name}" created successfully!`, {
    closeButton: true
  });

  await Promise.all([
    queryClient.invalidateQueries(projectQueries.single(project_slug))
  ]);
  throw redirect(`/project/${project_slug}/${data.name}`);
}

async function cloneEnvironment(
  project_slug: string,
  cloned_environment: string,
  formData: FormData
) {
  const userData = {
    name: formData.get("name")?.toString() ?? "",
    deploy_services: formData.get("deploy_services") === "on"
  };

  const { error, data } = await apiClient.POST(
    "/api/projects/{slug}/clone-environment/{env_slug}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          slug: project_slug,
          env_slug: cloned_environment
        }
      },
      body: userData
    }
  );

  if (error) {
    return {
      userData,
      errors: error
    };
  }

  toast.success(`Environment "${cloned_environment}" cloned successfully!`, {
    closeButton: true
  });

  await Promise.all([
    queryClient.invalidateQueries(projectQueries.single(project_slug))
  ]);
  throw redirect(`/project/${project_slug}/${data.name}`);
}

async function archiveEnvironment(project_slug: string, env_slug: string) {
  const apiResponse = await apiClient.DELETE(
    "/api/projects/{slug}/environment-details/{env_slug}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          slug: project_slug,
          env_slug
        }
      }
    }
  );

  if (apiResponse.error) {
    return {
      errors: apiResponse.error
    };
  }

  await Promise.all([
    queryClient.invalidateQueries(projectQueries.single(project_slug)),
    queryClient.invalidateQueries({
      predicate: (query) =>
        query.queryKey[0] === resourceQueries.search().queryKey[0]
    })
  ]);

  toast.success("Success", {
    closeButton: true,
    description: (
      <span>
        Environment `<strong>{env_slug}</strong>` has been successfully deleted.
      </span>
    )
  });

  throw redirect(
    href("/project/:projectSlug/settings/environments", {
      projectSlug: project_slug
    })
  );
}

function CreateEnvironmentFormDialog({
  environments
}: { environments: Project["environments"] }) {
  const [isOpen, setIsOpen] = React.useState(false);
  const fetcher = useFetcher<typeof clientAction>();
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const inputRef = React.useRef<React.ComponentRef<"input">>(null);

  const [data, setData] = React.useState(fetcher.data);
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(data?.errors);

  const [intent, setIntent] = React.useState<
    "create-environment" | "clone-environment"
  >("create-environment");

  React.useEffect(() => {
    setData(fetcher.data);

    // only focus on the correct input in case of error
    if (fetcher.state === "idle" && fetcher.data) {
      if (fetcher.data.errors) {
        const errors = getFormErrorsFromResponseData(fetcher.data.errors);
        const key = Object.keys(errors ?? {})[0];
        const field = formRef.current?.elements.namedItem(
          key
        ) as HTMLInputElement;
        field?.focus();
        return;
      }
      formRef.current?.reset();
      setIsOpen(false);
    }
  }, [fetcher.state, fetcher.data]);

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        setIsOpen(open);
        if (!open) {
          setData(undefined);
          setIntent("create-environment");
        }
      }}
    >
      <DialogTrigger asChild>
        <Button
          variant="secondary"
          className="inline-flex gap-1 items-center self-start"
        >
          <PlusIcon size={15} />
          Add new
        </Button>
      </DialogTrigger>
      <DialogContent className="gap-0">
        <DialogHeader className="pb-4">
          <DialogTitle>New environment</DialogTitle>

          <DialogDescription>
            All the changes will be isolated from other environments.
          </DialogDescription>
        </DialogHeader>

        {errors.non_field_errors && (
          <Alert variant="destructive" className="my-2">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{errors.non_field_errors}</AlertDescription>
          </Alert>
        )}

        <fetcher.Form
          className="flex flex-col w-full mb-5 gap-4"
          method="post"
          id="create-env-form"
          ref={formRef}
        >
          <FieldSet required name="name" errors={errors.name}>
            <FieldSetLabel>name</FieldSetLabel>
            <FieldSetInput ref={inputRef} placeholder="ex: staging" />
          </FieldSet>

          <FieldSet
            name="clone_environment"
            className="flex-1 inline-flex gap-2 flex-col"
          >
            <div className="inline-flex gap-2 items-start">
              <FieldSetCheckbox
                checked={intent === "clone-environment"}
                onCheckedChange={() =>
                  setIntent((prev) =>
                    prev === "clone-environment"
                      ? "create-environment"
                      : "clone-environment"
                  )
                }
                className="relative top-1"
              />

              <div className="flex flex-col gap-0.5">
                <FieldSetLabel className="inline-flex gap-1 items-center">
                  Clone environment ?
                </FieldSetLabel>

                <small className="text-grey text-sm">
                  Copy all the services, variables, and configuration from an
                  existing environment.
                </small>
              </div>
            </div>
          </FieldSet>

          {intent === "clone-environment" && (
            <>
              <hr className="border-border border-dashed" />
              <FieldSet
                name="clone_from"
                className="flex flex-col gap-2 flex-1"
              >
                <FieldSetLabel htmlFor="clone_from">
                  Source environment
                </FieldSetLabel>

                <FieldSetSelect name="clone_from">
                  <SelectTrigger id="clone_from">
                    <SelectValue placeholder="Select environment" />
                  </SelectTrigger>
                  <SelectContent className="z-999">
                    {environments.map((env) => (
                      <SelectItem value={env.name} key={env.id}>
                        {env.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </FieldSetSelect>
              </FieldSet>

              <FieldSet
                errors={errors.deploy_services}
                className="flex-1 inline-flex gap-2 flex-col"
              >
                <div className="inline-flex gap-2 items-start">
                  <FieldSetCheckbox
                    name="deploy_services"
                    className="relative top-1"
                  />

                  <div className="flex flex-col gap-1">
                    <FieldSetLabel>Deploy services ?</FieldSetLabel>
                    <small className="text-grey">
                      If checked, this will automatically issue a deploy for
                      each cloned service
                    </small>
                  </div>
                </div>
              </FieldSet>
            </>
          )}
        </fetcher.Form>

        <DialogFooter className="-mx-6 px-6 pt-4 ">
          <div className="flex items-center gap-4 w-full">
            <SubmitButton
              className={cn("inline-flex gap-1 items-center")}
              value="create_environment"
              name="intent"
              form="create-env-form"
              isPending={isPending}
            >
              {isPending ? (
                <>
                  <LoaderIcon className="animate-spin flex-none" size={15} />
                  <span>Creating environment...</span>
                </>
              ) : (
                <>
                  <span>Create environment</span>
                </>
              )}
            </SubmitButton>

            <Button
              variant="outline"
              onClick={() => {
                setIsOpen(false);
                setData(undefined);
              }}
            >
              Cancel
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

type EnvironmentRowProps = {
  environment: Project["environments"][number];
};
function EnvironmentItem({ environment: env }: EnvironmentRowProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const params = useParams<Route.ComponentProps["params"]>();
  const inputRef = React.useRef<React.ComponentRef<"input">>(null);
  const isPending = fetcher.state !== "idle";
  const [data, setData] = React.useState(fetcher.data);
  const errors = getFormErrorsFromResponseData(data?.errors);
  const navigate = useNavigate();
  const [isPasswordShown, setIsPasswordShown] = React.useState(false);

  const [accordionValue, setAccordionValue] = React.useState("");
  const isModifiable = !env.is_preview && env.name !== "production";

  React.useEffect(() => {
    setData(fetcher.data);

    if (fetcher.state === "idle" && fetcher.data) {
      if (fetcher.data.errors) {
        inputRef.current?.focus();
      } else {
        setAccordionValue("");
        navigate(
          href("/project/:projectSlug/settings", {
            projectSlug: params.projectSlug!
          }),
          { replace: true }
        );
      }
    }
  }, [fetcher.state, fetcher.data, params.projectSlug]);

  let preview_repo_path = env.preview_metadata?.repository_url
    ? new URL(env.preview_metadata?.repository_url).pathname.substring(1)
    : null;

  return (
    <>
      <div className="flex flex-col gap-1.5 flex-1 w-full ">
        <label htmlFor={`env-${env.id}`} className="sr-only">
          name
        </label>
        <div className="relative w-full flex flex-col md:flex-row items-start gap-2">
          <Accordion
            type="single"
            collapsible
            value={accordionValue}
            className="w-full"
            onValueChange={(state) => {
              setAccordionValue(state);
            }}
          >
            <AccordionItem
              value={`item-${env.id}`}
              className="border-none w-full"
            >
              <AccordionTrigger
                className={cn(
                  "w-full px-3 py-4 bg-muted rounded-md gap-2 flex flex-col items-start text-start pr-24",
                  "data-[state=open]:rounded-b-none [&[data-state=open]_svg]:rotate-90"
                )}
              >
                <div className="inline-flex gap-2 items-center flex-wrap">
                  <ChevronRightIcon size={15} className="text-grey flex-none" />
                  <span>{env.name}</span>
                  {env.name === "production" && (
                    <LockKeyholeIcon
                      className="text-grey !rotate-0"
                      size={15}
                    />
                  )}
                  {env.is_preview && (
                    <StatusBadge color="blue" pingState="hidden">
                      Preview
                    </StatusBadge>
                  )}
                </div>
              </AccordionTrigger>
              <AccordionContent className="border-border border-x border-b rounded-b-md p-4 mb-4">
                <fetcher.Form method="POST" className="flex flex-col gap-4">
                  <input
                    type="hidden"
                    name="current_environment"
                    value={env.name}
                  />

                  <FieldSet
                    required
                    errors={errors.name}
                    name={isModifiable ? "name" : undefined}
                    className="flex-1 inline-flex flex-col gap-1 w-full"
                  >
                    <FieldSetLabel>Name</FieldSetLabel>
                    <FieldSetInput
                      placeholder="ex: staging"
                      defaultValue={env.name}
                      disabled={!isModifiable}
                      className={cn(
                        "disabled:placeholder-shown:font-mono disabled:bg-muted",
                        "disabled:border-transparent disabled:opacity-100"
                      )}
                    />
                  </FieldSet>

                  {env.is_preview && env.preview_metadata && (
                    <div className="flex flex-col gap-5">
                      <hr className="border border-dashed border-border" />
                      <h3 className="text-base">Preview metadata</h3>

                      <div className="flex flex-col gap-2">
                        <div className="w-full flex flex-col gap-2">
                          <label
                            className="text-muted-foreground"
                            htmlFor="external_url"
                          >
                            Preview Trigger Source
                          </label>
                          <div className="flex flex-col gap-1 relative">
                            <Input
                              disabled
                              id="external_url"
                              defaultValue={env.preview_metadata.source_trigger}
                              className={cn(
                                "disabled:placeholder-shown:font-mono disabled:bg-muted",
                                "disabled:border-transparent disabled:opacity-100 disabled:select-none",
                                "text-transparent"
                              )}
                            />
                            <div className="absolute inset-y-0 px-3 text-sm flex items-center gap-1.5">
                              <span>{env.preview_metadata.source_trigger}</span>
                              {env.preview_metadata.source_trigger ===
                              "PULL_REQUEST" ? (
                                <GitPullRequestArrowIcon
                                  size={15}
                                  className="flex-none text-grey"
                                />
                              ) : (
                                <WebhookIcon
                                  size={15}
                                  className="flex-none text-grey"
                                />
                              )}
                            </div>
                          </div>
                        </div>

                        <div className="w-full flex flex-col gap-2">
                          <label
                            className="text-muted-foreground"
                            htmlFor="external_url"
                          >
                            External URL
                          </label>
                          <div className="flex flex-col gap-1">
                            <a
                              href={env.preview_metadata.external_url}
                              className="underline text-link inline-flex gap-1 items-center"
                            >
                              {env.preview_metadata.external_url}{" "}
                              <ExternalLinkIcon
                                size={15}
                                className="flex-none"
                              />
                            </a>
                          </div>
                        </div>

                        <div className="w-full flex flex-col gap-2">
                          <FieldSet
                            disabled
                            className="flex-1 inline-flex gap-2 flex-col"
                          >
                            <div className="inline-flex gap-2 items-start">
                              <FieldSetCheckbox
                                checked={env.preview_metadata.auto_teardown}
                                className="relative top-1"
                              />

                              <div className="flex flex-col gap-0.5">
                                <FieldSetLabel className="inline-flex gap-1 items-center">
                                  Auto teardown
                                </FieldSetLabel>

                                <small className="text-grey text-sm">
                                  Automatically remove preview environments when
                                  the associated branch or pull request is
                                  deleted.
                                </small>
                              </div>
                            </div>
                          </FieldSet>
                        </div>
                      </div>

                      <fieldset className="w-full flex flex-col gap-2">
                        <legend>Git source</legend>
                        <p className="text-gray-400">
                          The repository that triggered this preview environment
                        </p>
                        <div className="w-full flex flex-col gap-2">
                          <label
                            className="text-muted-foreground"
                            htmlFor="external_url"
                          >
                            Git app
                          </label>
                          <div className="flex flex-col gap-1 relative">
                            <Input
                              disabled
                              id="external_url"
                              defaultValue={
                                env.preview_metadata.git_app.github?.name ??
                                env.preview_metadata.git_app.gitlab?.name
                              }
                              className={cn(
                                "disabled:placeholder-shown:font-mono disabled:bg-muted",
                                "disabled:border-transparent disabled:opacity-100 disabled:select-none",
                                "text-transparent"
                              )}
                            />
                            <div className="absolute inset-y-0 px-3 text-sm flex items-center gap-1.5">
                              <span>
                                {env.preview_metadata.git_app.github?.name ??
                                  env.preview_metadata.git_app.gitlab?.name}
                              </span>
                              {env.preview_metadata.git_app.github && (
                                <GithubIcon
                                  size={15}
                                  className="flex-none text-grey"
                                />
                              )}
                              {env.preview_metadata.git_app.gitlab && (
                                <GitlabIcon
                                  size={15}
                                  className="flex-none text-grey"
                                />
                              )}
                            </div>
                          </div>
                        </div>

                        <div className="w-full flex flex-col gap-2">
                          <label
                            className="text-muted-foreground"
                            htmlFor="external_url"
                          >
                            Repository
                          </label>
                          <div className="flex flex-col gap-1 relative">
                            <Input
                              disabled
                              id="external_url"
                              defaultValue={preview_repo_path}
                              className={cn(
                                "disabled:placeholder-shown:font-mono disabled:bg-muted",
                                "disabled:border-transparent disabled:opacity-100 disabled:select-none",
                                "text-transparent"
                              )}
                            />
                            <div className="absolute inset-y-0 px-3 text-sm flex items-center gap-1.5">
                              <span>{preview_repo_path}</span>
                            </div>
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                          <div className="w-full flex flex-col gap-2">
                            <label
                              className="text-muted-foreground"
                              htmlFor="external_url"
                            >
                              Branch name
                            </label>
                            <div className="flex flex-col gap-1 relative">
                              <Input
                                disabled
                                id="external_url"
                                defaultValue={env.preview_metadata.branch_name}
                                className={cn(
                                  "disabled:placeholder-shown:font-mono disabled:bg-muted",
                                  "disabled:border-transparent disabled:opacity-100 disabled:select-none",
                                  "text-transparent"
                                )}
                              />
                              <div className="absolute inset-y-0 px-3 text-sm flex items-center gap-1.5">
                                <span>{env.preview_metadata.branch_name}</span>
                              </div>
                            </div>
                          </div>

                          <div className="w-full flex flex-col gap-2">
                            <label
                              className="text-muted-foreground"
                              htmlFor="external_url"
                            >
                              Commit SHA
                            </label>
                            <div className="flex flex-col gap-1 relative">
                              <Input
                                disabled
                                id="external_url"
                                defaultValue={env.preview_metadata.commit_sha}
                                className={cn(
                                  "disabled:placeholder-shown:font-mono disabled:bg-muted",
                                  "disabled:border-transparent disabled:opacity-100 disabled:select-none",
                                  "text-transparent"
                                )}
                              />
                              <div className="absolute inset-y-0 px-3 text-sm flex items-center gap-1.5">
                                <span>
                                  {env.preview_metadata.commit_sha.substring(
                                    0,
                                    7
                                  )}
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </fieldset>

                      {env.preview_metadata.auth_enabled && (
                        <fieldset className="w-full flex flex-col gap-2">
                          <legend>Authentication</legend>
                          <p className="text-gray-400">
                            Your environment is protected with basic auth
                          </p>

                          <label
                            className="text-muted-foreground"
                            htmlFor="auth.user"
                          >
                            Username
                          </label>
                          <div className="flex flex-col gap-1">
                            <Input
                              disabled
                              id="auth.user"
                              defaultValue={env.preview_metadata.auth_user}
                              className={cn(
                                "disabled:placeholder-shown:font-mono disabled:bg-muted",
                                "disabled:border-transparent disabled:opacity-100 disabled:select-none"
                              )}
                            />
                          </div>

                          <label
                            className="text-muted-foreground"
                            htmlFor="credentials.password"
                          >
                            Password
                          </label>
                          <div className="flex gap-2 items-start">
                            <div className="inline-flex flex-col gap-1 flex-1">
                              <Input
                                disabled
                                type={isPasswordShown ? "text" : "password"}
                                defaultValue={
                                  env.preview_metadata.auth_password
                                }
                                name="credentials.password"
                                id="credentials.password"
                                className={cn(
                                  "disabled:placeholder-shown:font-mono disabled:bg-muted ",
                                  "disabled:border-transparent disabled:opacity-100"
                                )}
                              />
                            </div>

                            <TooltipProvider>
                              <Tooltip delayDuration={0}>
                                <TooltipTrigger asChild>
                                  <Button
                                    variant="outline"
                                    type="button"
                                    onClick={() =>
                                      setIsPasswordShown(!isPasswordShown)
                                    }
                                    className="p-4"
                                  >
                                    {isPasswordShown ? (
                                      <EyeOffIcon
                                        size={15}
                                        className="flex-none"
                                      />
                                    ) : (
                                      <EyeIcon
                                        size={15}
                                        className="flex-none"
                                      />
                                    )}
                                    <span className="sr-only">
                                      {isPasswordShown ? "Hide" : "Show"}{" "}
                                      password
                                    </span>
                                  </Button>
                                </TooltipTrigger>
                                <TooltipContent>
                                  {isPasswordShown ? "Hide" : "Show"} password
                                </TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                          </div>
                        </fieldset>
                      )}
                    </div>
                  )}

                  <div className="flex justify-end items-center gap-2 border-t pt-4 px-4 -mx-4 border-border">
                    <SubmitButton
                      variant="secondary"
                      isPending={isPending}
                      className="inline-flex gap-1"
                      name="intent"
                      value="rename_environment"
                      disabled={!isModifiable}
                    >
                      {isPending ? (
                        <>
                          <span>Updating...</span>
                          <LoaderIcon className="animate-spin" size={15} />
                        </>
                      ) : (
                        <>
                          Update
                          <CheckIcon size={15} />
                        </>
                      )}
                    </SubmitButton>
                    {env.name !== "production" && (
                      <EnvironmentDeleteFormDialog environment={env.name} />
                    )}
                  </div>
                </fetcher.Form>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </div>
      </div>
    </>
  );
}

function EnvironmentDeleteFormDialog({ environment }: { environment: string }) {
  const params = useParams<Route.ComponentProps["params"]>();
  const [isOpen, setIsOpen] = React.useState(false);
  const fetcher = useFetcher<typeof clientAction>();
  const formRef = React.useRef<React.ComponentRef<"form">>(null);

  const [data, setData] = React.useState(fetcher.data);
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(data?.errors);
  const navigate = useNavigate();

  React.useEffect(() => {
    setData(fetcher.data);

    // only focus on the correct input in case of error
    if (fetcher.state === "idle" && fetcher.data) {
      if (fetcher.data.errors) {
        const errors = getFormErrorsFromResponseData(fetcher.data.errors);
        const key = Object.keys(errors ?? {})[0];
        const field = formRef.current?.elements.namedItem(
          key
        ) as HTMLInputElement;
        field?.focus();
        return;
      }
      formRef.current?.reset();

      setIsOpen(false);
      navigate(
        href("/project/:projectSlug/settings/environments", {
          projectSlug: params.projectSlug!
        }),
        { replace: true }
      );
    }
  }, [fetcher.state, fetcher.data, params.projectSlug]);

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        setIsOpen(open);
        if (!open) {
          setData(undefined);
        }
      }}
    >
      <DialogTrigger asChild>
        <Button
          variant="destructive"
          type="button"
          className={cn(
            "text-sm border-0  inline-flex items-center gap-1  px-2.5 py-0.5"
          )}
        >
          <span>Delete</span>
          <Trash2Icon size={15} className="flex-none" />
        </Button>
      </DialogTrigger>
      <DialogContent className="gap-0">
        <DialogHeader className="pb-4">
          <DialogTitle>Delete this environment ?</DialogTitle>

          <Alert variant="danger" className="my-5">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Attention !</AlertTitle>
            <AlertDescription>
              Deleting this environment will also remove all its services and
              their deployments. This action <strong>CANNOT</strong> be undone.
            </AlertDescription>
          </Alert>

          <DialogDescription className="inline-flex gap-1 items-center flex-wrap">
            <span className="whitespace-nowrap">Please type</span>
            <CopyButton
              variant="outline"
              size="sm"
              showLabel
              value={`${params.projectSlug}/${environment}`}
              label={`${params.projectSlug}/${environment}`}
            />
            <span className="whitespace-nowrap">to confirm :</span>
          </DialogDescription>
        </DialogHeader>

        {errors.non_field_errors && (
          <Alert variant="destructive">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{errors.non_field_errors}</AlertDescription>
          </Alert>
        )}

        <fetcher.Form
          className="flex flex-col w-full mb-5 gap-1"
          method="post"
          id="delete-form"
          ref={formRef}
        >
          <FieldSet name="name" errors={errors.name}>
            <FieldSetInput />
          </FieldSet>

          <input type="hidden" name="environment" value={environment} />
        </fetcher.Form>

        <DialogFooter className="-mx-6 px-6 pt-4">
          <div className="flex items-center gap-4 w-full">
            <SubmitButton
              variant="destructive"
              className={cn(
                "inline-flex gap-1 items-center",
                isPending ? "bg-red-400" : "bg-red-500"
              )}
              value="archive_environment"
              name="intent"
              form="delete-form"
              isPending={isPending}
            >
              {isPending ? (
                <>
                  <LoaderIcon className="animate-spin flex-none" size={15} />
                  <span>Deleting...</span>
                </>
              ) : (
                <>
                  <span>Delete</span>
                </>
              )}
            </SubmitButton>

            <Button
              variant="outline"
              onClick={() => {
                setIsOpen(false);
                setData(undefined);
              }}
            >
              Cancel
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
