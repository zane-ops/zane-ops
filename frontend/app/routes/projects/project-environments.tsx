import {
  AlertCircleIcon,
  CheckIcon,
  ChevronRightIcon,
  EditIcon,
  EllipsisVerticalIcon,
  ExternalLinkIcon,
  EyeIcon,
  EyeOffIcon,
  LoaderIcon,
  LockKeyholeIcon,
  PencilLineIcon,
  PlusIcon,
  Trash2Icon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { flushSync } from "react-dom";
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
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
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
import { Input } from "~/components/ui/input";
import {
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "~/components/ui/select";

import { env } from "process";
import { Code } from "~/components/code";
import { StatusBadge } from "~/components/status-badge";
import { Badge } from "~/components/ui/badge";
import {
  Menubar,
  MenubarContent,
  MenubarContentItem,
  MenubarMenu,
  MenubarTrigger
} from "~/components/ui/menubar";
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
  getFormErrorsFromResponseData
} from "~/lib/utils";
import { queryClient } from "~/root";
import { getCsrfTokenHeader, pluralize } from "~/utils";
import type { clientAction as variablesClientAction } from "../environments/environment-variables";
import type { Route } from "./+types/project-environments";

export default function ProjectEnvironmentsPage({
  matches: {
    "2": {
      data: { project }
    }
  }
}: Route.ComponentProps) {
  return (
    <section className="flex gap-1 scroll-mt-20 px-4">
      <div className="w-full flex flex-col gap-5 pt-1 pb-14">
        <h2 className="text-xl">Environments</h2>

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
    <div className="flex flex-col gap-6 w-full">
      {environments.map((env, index) => (
        <section key={env.id} className="flex flex-col gap-2">
          {index > 0 && <hr className="border border-dashed border-border" />}
          <EnvironmentRow environment={env} />
        </section>
      ))}

      <CreateEnvironmentFormDialog environments={environments} />
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
        }
      }}
    >
      <DialogTrigger asChild>
        <Button className="inline-flex gap-1 items-center self-start">
          <PlusIcon size={15} />
          New Environment
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

          <hr className="border-border border-dashed my-1" />
          <FieldSet name="clone_from" className="flex flex-col gap-2 flex-1">
            <FieldSetLabel
              htmlFor="clone_from"
              className="text-lg dark:text-card-foreground"
            >
              Clone environment
            </FieldSetLabel>
            <p className="text-grey text-sm">
              Selecting one environment will copy all the services, variables,
              and configuration from that environment.
            </p>
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
                <FieldSetLabel className="inline-flex gap-1 items-center">
                  Deploy services ?
                </FieldSetLabel>
                <small className="text-grey">
                  If checked, this will automatically issue a deploy for each
                  cloned service
                </small>
              </div>
            </div>
          </FieldSet>
        </fetcher.Form>

        <DialogFooter className="-mx-6 px-6 pt-4">
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
function EnvironmentRow({ environment: env }: EnvironmentRowProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const params = useParams<Route.ComponentProps["params"]>();
  const [isEditing, setIsEditing] = React.useState(false);
  const inputRef = React.useRef<React.ComponentRef<"input">>(null);
  const isPending = fetcher.state !== "idle";
  const [data, setData] = React.useState(fetcher.data);
  const errors = getFormErrorsFromResponseData(data?.errors);
  const navigate = useNavigate();

  React.useEffect(() => {
    setData(fetcher.data);

    if (fetcher.state === "idle" && fetcher.data) {
      if (fetcher.data.errors) {
        inputRef.current?.focus();
      } else {
        setIsEditing(false);
        navigate(
          href("/project/:projectSlug/settings", {
            projectSlug: params.projectSlug!
          }),
          { replace: true }
        );
      }
    }
  }, [fetcher.state, fetcher.data, params.projectSlug]);

  return (
    <>
      <fetcher.Form
        method="POST"
        className="flex flex-col gap-1.5 flex-1 w-full "
      >
        <label htmlFor={`env-${env.id}`} className="sr-only">
          name
        </label>
        <div className="relative w-full flex flex-col md:flex-row items-start gap-2">
          <input type="hidden" name="current_environment" value={env.name} />

          <div className="relative w-full">
            <Input
              id={`env-${env.id}`}
              name="name"
              ref={inputRef}
              placeholder="ex: staging"
              defaultValue={env.name}
              disabled={!isEditing}
              aria-labelledby="slug-error"
              aria-invalid={Boolean(errors.name)}
              className={cn(
                "disabled:placeholder-shown:font-mono disabled:bg-muted",
                "disabled:border-transparent disabled:opacity-100",
                "disabled:text-transparent"
              )}
            />
            {!isEditing && (
              <span className="absolute inset-y-0 left-3 inline-flex gap-2 items-center text-sm">
                {env.name}
                {env.is_preview && (
                  <StatusBadge color="blue" pingState="hidden">
                    Preview
                  </StatusBadge>
                )}
              </span>
            )}
          </div>

          {env.name === "production" ? (
            <div className="absolute inset-y-0 left-0 text-sm py-0 gap-1 flex h-full items-center px-3.5 text-grey">
              <span className="invisible select-none" aria-hidden="true">
                production
              </span>
              <LockKeyholeIcon size={15} />
            </div>
          ) : !isEditing ? (
            <div className="absolute inset-y-0 right-0 flex items-center gap-1">
              {!env.is_preview && (
                <Button
                  variant="outline"
                  type="button"
                  onClick={() => {
                    flushSync(() => {
                      setIsEditing(true);
                    });
                    inputRef.current?.focus();
                  }}
                  className={cn(
                    "text-sm py-0 border-0",
                    "bg-inherit inline-flex items-center gap-2 border-muted-foreground px-2.5 py-0.5"
                  )}
                >
                  <span>rename</span>
                  <PencilLineIcon size={15} />
                </Button>
              )}
              <EnvironmentDeleteFormDialog environment={env.name} />
            </div>
          ) : (
            <div className="flex gap-2 ">
              <SubmitButton
                isPending={isPending}
                variant="outline"
                className="bg-inherit"
                name="intent"
                value="rename_environment"
              >
                {isPending ? (
                  <>
                    <LoaderIcon className="animate-spin" size={15} />
                    <span className="sr-only">Renaming environment...</span>
                  </>
                ) : (
                  <>
                    <CheckIcon size={15} className="flex-none" />
                    <span className="sr-only">Rename environment</span>
                  </>
                )}
              </SubmitButton>
              <Button
                onClick={(ev) => {
                  ev.currentTarget.form?.reset();
                  setIsEditing(false);
                  setData(undefined);
                }}
                variant="outline"
                className="bg-inherit"
                type="reset"
              >
                <XIcon size={15} className="flex-none" />
                <span className="sr-only">Cancel</span>
              </Button>
            </div>
          )}
        </div>

        {errors.name && (
          <span id="name-error" className="text-red-500 text-sm">
            {errors.name}
          </span>
        )}
      </fetcher.Form>
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
          variant="outline"
          type="button"
          className={cn(
            "text-sm py-0 border-0",
            "bg-inherit inline-flex items-center gap-2 border-muted-foreground px-2.5 py-0.5",
            "text-red-400"
          )}
        >
          <span>delete</span>
          <Trash2Icon size={15} className="flex-none text-red-400" />
        </Button>
      </DialogTrigger>
      <DialogContent className="gap-0">
        <DialogHeader className="pb-4">
          <DialogTitle>Delete this environment ?</DialogTitle>

          <Alert variant="danger" className="my-5">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Attention !</AlertTitle>
            <AlertDescription>
              Deleting this environment will also delete all its services and
              delete all the deployments related to the services, This action is
              irreversible.
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
