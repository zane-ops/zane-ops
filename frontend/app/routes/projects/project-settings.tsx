import {
  AlertCircleIcon,
  CheckIcon,
  ChevronRightIcon,
  EditIcon,
  EllipsisVerticalIcon,
  ExternalLinkIcon,
  EyeIcon,
  EyeOffIcon,
  FlameIcon,
  InfoIcon,
  LoaderIcon,
  LockKeyholeIcon,
  NetworkIcon,
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
import { Textarea } from "~/components/ui/textarea";

import { Code } from "~/components/code";
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
import { type Project, projectQueries, resourceQueries } from "~/lib/queries";
import {
  type ErrorResponseFromAPI,
  cn,
  getFormErrorsFromResponseData
} from "~/lib/utils";
import { queryClient } from "~/root";
import { getCsrfTokenHeader, pluralize } from "~/utils";
import type { Route } from "./+types/project-settings";
import type { clientAction as variablesClientAction } from "./project-env-variables";

export default function ProjectSettingsPage({
  params,
  matches: {
    "2": {
      data: { project }
    }
  }
}: Route.ComponentProps) {
  return (
    <div className="my-6 grid lg:grid-cols-12 gap-10 relative">
      <div className="lg:col-span-10 flex flex-col">
        <section id="details" className="flex gap-1 scroll-mt-20">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <InfoIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>

          <div className="w-full flex flex-col gap-5 pt-1 pb-8">
            <h2 className="text-lg text-grey">Details</h2>

            <ProjectDetailsForm
              project_slug={params.projectSlug}
              description={project.description ?? ""}
            />
          </div>
        </section>

        <section id="danger" className="flex gap-1 scroll-mt-20">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
              <NetworkIcon size={15} className="flex-none text-grey" />
            </div>
            <div className="h-full border border-grey/50"></div>
          </div>
          <div className="w-full flex flex-col gap-5 pt-1 pb-14">
            <h2 className="text-lg text-grey">Environments</h2>

            <p className="text-grey">
              Each environment provides a separate instance of each
              service.&nbsp;
              <a
                href="#"
                target="_blank"
                className="text-link underline inline-flex gap-1 items-center"
              >
                Read the docs <ExternalLinkIcon size={12} />
              </a>
            </p>
            <EnvironmentList environments={project.environments} />
          </div>
        </section>

        <section id="danger" className="flex gap-1 scroll-mt-20">
          <div className="w-16 hidden md:flex flex-col items-center">
            <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-red-500">
              <FlameIcon size={15} className="flex-none text-red-500" />
            </div>
          </div>
          <div className="w-full flex flex-col gap-5 pt-1 pb-14">
            <h2 className="text-lg text-red-400">Danger Zone</h2>
            <ProjectDangerZoneForm project_slug={params.projectSlug} />
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
    case "update_project": {
      return updateProject(params.projectSlug, formData);
    }
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
    case "archive_project": {
      if (
        formData.get("project_slug")?.toString().trim() !== params.projectSlug
      ) {
        return {
          errors: {
            type: "validation_error",
            errors: [
              {
                attr: "project_slug",
                code: "invalid",
                detail: "The project slug does not match"
              }
            ]
          } satisfies ErrorResponseFromAPI
        };
      }
      return archiveProject(params.projectSlug);
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

async function updateProject(project_slug: string, formData: FormData) {
  const userData = {
    slug: formData.get("slug")?.toString() ?? "",
    description: formData.get("description")?.toString() || undefined
  };
  const apiResponse = await apiClient.PATCH("/api/projects/{slug}/", {
    headers: {
      ...(await getCsrfTokenHeader())
    },
    params: {
      path: {
        slug: project_slug
      }
    },
    body: userData
  });

  if (apiResponse.error) {
    return {
      userData,
      errors: apiResponse.error
    };
  }

  queryClient.invalidateQueries(projectQueries.single(project_slug));
  toast.success("Project updated successfully!", { closeButton: true });

  if (apiResponse.data.slug !== project_slug) {
    queryClient.setQueryData(
      projectQueries.single(userData.slug).queryKey,
      apiResponse.data
    );
    throw redirect(`/project/${userData.slug}/production/settings`);
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
        projectQueries.serviceList(project_slug, currentEnvironment)
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

async function archiveProject(project_slug: string) {
  const apiResponse = await apiClient.DELETE("/api/projects/{slug}/", {
    headers: {
      ...(await getCsrfTokenHeader())
    },
    params: {
      path: {
        slug: project_slug
      }
    }
  });

  if (apiResponse.error) {
    return {
      errors: apiResponse.error
    };
  }

  queryClient.invalidateQueries(projectQueries.single(project_slug));
  queryClient.invalidateQueries({
    predicate: (query) =>
      query.queryKey[0] === resourceQueries.search().queryKey[0] ||
      query.queryKey[0] === projectQueries.list().queryKey[0]
  });

  toast.success("Success", {
    closeButton: true,
    description: (
      <span>
        Project `<strong>{project_slug}</strong>` has been successfully deleted.
      </span>
    )
  });
  throw redirect(`/`);
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

  return {
    data: {
      name: env_slug
    }
  };
}

type ProjectDetailsFormProps = {
  description: string;
  project_slug: string;
};

function ProjectDetailsForm({
  description,
  project_slug
}: ProjectDetailsFormProps) {
  const fetcher = useFetcher<typeof clientAction>();
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

      <fieldset className="flex flex-col gap-1.5 flex-1">
        <label htmlFor="slug">Project slug</label>
        <Input
          id="slug"
          name="slug"
          placeholder="project slug"
          defaultValue={project_slug}
          aria-labelledby="slug-error"
          aria-invalid={!!errors.slug}
        />

        {errors.slug && (
          <span id="slug-error" className="text-red-500 text-sm">
            {errors.slug}
          </span>
        )}
      </fieldset>

      <fieldset className="my-2 flex flex-col gap-1">
        <label htmlFor="description">Description</label>
        <Textarea
          className="placeholder:text-gray-400"
          name="description"
          id="description"
          placeholder="Ex: A self hosted PaaS"
          defaultValue={description}
          aria-describedby="description-error"
        />
        {errors.description && (
          <span id="description-error" className="text-red-500 text-sm">
            {errors.description}
          </span>
        )}
      </fieldset>

      <SubmitButton
        isPending={isPending}
        variant="secondary"
        className="self-start"
        name="intent"
        value="update_project"
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

function ProjectDangerZoneForm({ project_slug }: { project_slug: string }) {
  const fetcher = useFetcher<typeof clientAction>();

  return (
    <fetcher.Form method="post" className="flex flex-col gap-2 items-start">
      <DeleteConfirmationFormDialog project_slug={project_slug} />
    </fetcher.Form>
  );
}

function DeleteConfirmationFormDialog({
  project_slug
}: { project_slug: string }) {
  const [isOpen, setIsOpen] = React.useState(false);
  const fetcher = useFetcher<typeof clientAction>();
  const formRef = React.useRef<React.ComponentRef<"form">>(null);

  const [data, setData] = React.useState(fetcher.data);
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(data?.errors);

  React.useEffect(() => {
    setData(fetcher.data);

    // only focus on the correct input in case of error
    if (fetcher.state === "idle" && fetcher.data && !fetcher.data.errors) {
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
        <Button
          variant="destructive"
          type="button"
          className={cn("inline-flex gap-1 items-center")}
        >
          <Trash2Icon size={15} className="flex-none" />
          <span>Delete this project</span>
        </Button>
      </DialogTrigger>
      <DialogContent className="gap-0">
        <DialogHeader className="pb-4">
          <DialogTitle>Delete this project ?</DialogTitle>

          <Alert variant="danger" className="my-5">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Attention !</AlertTitle>
            <AlertDescription>
              Deleting this project will also delete all its services and delete
              all the deployments related to the services, This action is
              irreversible.
            </AlertDescription>
          </Alert>

          <DialogDescription>
            Please type <strong>{project_slug}</strong> to confirm :
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
          <FieldSet name="project_slug" errors={errors.project_slug}>
            <FieldSetInput />
          </FieldSet>
        </fetcher.Form>

        <DialogFooter className="-mx-6 px-6 pt-4">
          <div className="flex items-center gap-4 w-full">
            <SubmitButton
              variant="destructive"
              className={cn(
                "inline-flex gap-1 items-center",
                isPending ? "bg-red-400" : "bg-red-500"
              )}
              value="archive_project"
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
          href("/project/:projectSlug/:envSlug/settings", {
            projectSlug: params.projectSlug!,
            envSlug: fetcher.data.data.name
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
              "disabled:border-transparent disabled:opacity-100"
            )}
          />

          {env.name === "production" ? (
            <div className="absolute inset-y-0 left-0 text-sm py-0 gap-1 flex h-full items-center px-3.5 text-grey">
              <span className="invisible select-none" aria-hidden="true">
                production
              </span>
              <LockKeyholeIcon size={15} />
            </div>
          ) : !isEditing ? (
            <div className="absolute inset-y-0 right-0 flex items-center gap-1">
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

      {/* TODO : later */}
      <Accordion type="single" collapsible className="border-t border-border">
        <AccordionItem value="system">
          <AccordionTrigger className="text-muted-foreground font-normal text-sm hover:underline">
            <ChevronRightIcon className="h-4 w-4 shrink-0 transition-transform duration-200" />
            {env.variables.length === 0 ? (
              <>No shared variables</>
            ) : (
              <>
                {env.variables.length} shared&nbsp;
                {pluralize("variable", env.variables.length)} in {env.name}
              </>
            )}
          </AccordionTrigger>
          <AccordionContent className="flex flex-col gap-2">
            <p className="text-muted-foreground pb-4 border-border">
              Shared variables are inherited by all the services in this
              environment. If a service has the same variable, that will take
              precedence over the variable defined in this environment. You can
              reference these variables in services with{" "}
              <Code>{"{{env.VARIABLE_NAME}}"}</Code>.
            </p>
            <div className="flex flex-col gap-2 px-2">
              <EditVariableForm env_slug={env.name} editType="add" />

              {env.variables.map((variable) => (
                <EnVariableRow
                  key={variable.id}
                  name={variable.key}
                  value={variable.value}
                  id={variable.id}
                  env_slug={env.name}
                />
              ))}
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
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

          <DialogDescription className="inline-flex gap-1 items-center">
            <span>Please type</span>
            <CopyButton
              variant="outline"
              size="sm"
              showLabel
              value={`${params.projectSlug}/${environment}`}
              label={`${params.projectSlug}/${environment}`}
            />
            <span>to confirm :</span>
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

type EnvVariableRowProps = {
  id: string;
  name: string;
  value: string;
  env_slug: string;
};

function EnVariableRow({ name, value, id, env_slug }: EnvVariableRowProps) {
  const [isEnvValueShown, setIsEnvValueShown] = React.useState(false);
  const [isEditing, setIsEditing] = React.useState(false);
  const [isOpen, setIsOpen] = React.useState(false);

  return (
    <div
      className={cn(
        "grid gap-4 items-center md:grid-cols-7 grid-cols-3 group pl-4 pt-2 md:py-1",
        isEditing && "items-start"
      )}
    >
      {isEditing ? (
        <EditVariableForm
          name={name}
          value={value}
          id={id}
          env_slug={env_slug}
          quitEditMode={() => setIsEditing(false)}
        />
      ) : (
        <>
          <div className={cn("col-span-3 md:col-span-2 flex flex-col")}>
            <span className="font-mono break-all">{name}</span>
          </div>

          <div className="col-span-2 font-mono flex items-center gap-2 md:col-span-4">
            {isEnvValueShown ? (
              <p className="whitespace-nowrap overflow-x-auto">
                {value.length > 0 ? (
                  value
                ) : (
                  <span className="text-grey font-mono">{`<empty>`}</span>
                )}
              </p>
            ) : (
              <span className="relative top-1">*********</span>
            )}
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    onClick={() => setIsEnvValueShown(!isEnvValueShown)}
                    className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                  >
                    {isEnvValueShown ? (
                      <EyeOffIcon size={15} className="flex-none" />
                    ) : (
                      <EyeIcon size={15} className="flex-none" />
                    )}
                    <span className="sr-only">
                      {isEnvValueShown ? "Hide" : "Reveal"} variable value
                    </span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {isEnvValueShown ? "Hide" : "Reveal"} variable value
                </TooltipContent>
              </Tooltip>

              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <CopyButton
                    variant="ghost"
                    value={value}
                    label="Copy variable value"
                  />
                </TooltipTrigger>
                <TooltipContent>Copy variable value</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </>
      )}

      {!isEditing && (
        <div className="flex justify-end">
          <DeleteVariableConfirmationDialog
            env_slug={env_slug}
            id={id}
            name={name}
            isOpen={isOpen}
            onOpenChange={setIsOpen}
          />
          <Menubar className="border-none h-auto w-fit">
            <MenubarMenu>
              <MenubarTrigger
                className="flex justify-center items-center gap-2"
                asChild
              >
                <Button
                  variant="ghost"
                  className="px-2.5 py-0.5 hover:bg-inherit"
                >
                  <EllipsisVerticalIcon size={15} />
                </Button>
              </MenubarTrigger>
              <MenubarContent
                side="bottom"
                align="start"
                className="border min-w-0 mx-9 border-border"
              >
                <MenubarContentItem
                  icon={EditIcon}
                  text="Edit"
                  onClick={() => setIsEditing(true)}
                />
                <MenubarContentItem
                  icon={Trash2Icon}
                  text="Delete"
                  className="text-red-400"
                  onClick={() => setIsOpen(true)}
                />
              </MenubarContent>
            </MenubarMenu>
          </Menubar>
        </div>
      )}
    </div>
  );
}

type DeleteVariableConfirmationDialogProps = {
  id: string;
  env_slug: string;
  name: string;
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
};

function DeleteVariableConfirmationDialog({
  id,
  env_slug,
  name,
  isOpen,
  onOpenChange
}: DeleteVariableConfirmationDialogProps) {
  const fetcher = useFetcher<typeof variablesClientAction>();
  const isPending = fetcher.state !== "idle";

  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  React.useEffect(() => {
    if (fetcher.state === "idle" && fetcher.data && !fetcher.data.errors) {
      onOpenChange(false);
    }
  }, [fetcher.state, fetcher.data]);

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        onOpenChange(open);
      }}
    >
      <DialogContent className="gap-0">
        <DialogHeader className="">
          <DialogTitle>Delete this shared variable ?</DialogTitle>

          <DialogDescription className="my-4 text-card-foreground text-base leading-6.5">
            Are you sure you want to delete <Code>`{name}`</Code> ? This will
            remove it from all the services in the&nbsp;
            <Code>{env_slug}</Code> environment.
          </DialogDescription>
        </DialogHeader>

        {errors.non_field_errors && (
          <Alert variant="destructive">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{errors.non_field_errors}</AlertDescription>
          </Alert>
        )}

        <DialogFooter className="-mx-6 px-6 pt-4">
          <fetcher.Form
            method="post"
            action="../variables"
            className="flex items-center gap-4 w-full"
          >
            <input type="hidden" name="variable_id" value={id} />
            <input type="hidden" name="env_slug" value={env_slug} />
            <SubmitButton
              variant="destructive"
              className={cn(
                "inline-flex gap-1 items-center",
                isPending ? "bg-red-400" : "bg-red-500"
              )}
              value="delete-env-variable"
              name="intent"
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
              type="button"
              variant="outline"
              onClick={() => {
                onOpenChange(false);
              }}
            >
              Cancel
            </Button>
          </fetcher.Form>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

type EditVariableFormProps = {
  name?: string;
  value?: string;
  id?: string | null;
  env_slug: string;
  editType?: "add" | "update";
  quitEditMode?: () => void;
};

function EditVariableForm({
  name,
  value,
  id,
  env_slug,
  editType = "update",
  quitEditMode
}: EditVariableFormProps) {
  const fetcher = useFetcher<typeof variablesClientAction>();
  const idPrefix = React.useId();
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);
  const formRef = React.useRef<React.ComponentRef<"form">>(null);

  React.useEffect(() => {
    // only focus on the correct input in case of error
    if (fetcher.state === "idle" && fetcher.data) {
      const nameInput = formRef.current?.[
        "variable-name"
      ] as HTMLInputElement | null;

      if (fetcher.data.errors) {
        const valueInput = formRef.current?.[
          "variable-value"
        ] as HTMLInputElement | null;

        if (errors.key) {
          nameInput?.focus();
        }
        if (errors.value) {
          valueInput?.focus();
        }

        return;
      }

      formRef.current?.reset();
      nameInput?.focus();
      quitEditMode?.();
    }
  }, [fetcher.state, fetcher.data, errors]);

  return (
    <fetcher.Form
      method="post"
      action="../variables"
      ref={formRef}
      className="col-span-3 md:col-span-7 flex flex-col md:flex-row items-start gap-4 pr-4"
    >
      {id && <input type="hidden" name="variable_id" value={id} />}

      <input type="hidden" name="env_slug" value={env_slug} />

      <fieldset className={cn("inline-flex flex-col gap-1 w-full md:w-2/7")}>
        <label id={`${idPrefix}-name`} className="sr-only">
          variable name
        </label>
        <Input
          placeholder="VARIABLE_NAME"
          defaultValue={name}
          autoFocus={editType === "add"}
          id="variable-name"
          name="key"
          className="font-mono"
          aria-labelledby={`${idPrefix}-name-error`}
          aria-invalid={!!errors.key}
        />
        {errors.key && (
          <span id={`${idPrefix}-name-error`} className="text-red-500 text-sm">
            {errors.key}
          </span>
        )}
      </fieldset>

      <fieldset className="flex-1 inline-flex flex-col gap-1 w-full">
        <label id={`${idPrefix}-value`} className="sr-only">
          variable value
        </label>
        <Input
          autoFocus={editType === "update"}
          placeholder="value"
          id="variable-value"
          defaultValue={value}
          name="value"
          className="font-mono"
          aria-labelledby={`${idPrefix}-value-error`}
          aria-invalid={!!errors.value}
        />
        {errors.value && (
          <span id={`${idPrefix}-value-error`} className="text-red-500 text-sm">
            {errors.value}
          </span>
        )}
      </fieldset>

      <div className="flex gap-3">
        {editType === "add" ? (
          <SubmitButton
            isPending={isPending}
            variant="default"
            name="intent"
            value="add-env-variable"
          >
            {isPending ? (
              <>
                <LoaderIcon className="animate-spin" size={15} />
                <span>Adding...</span>
              </>
            ) : (
              <>
                <CheckIcon size={15} className="flex-none" />
                <span>Add</span>
              </>
            )}
          </SubmitButton>
        ) : (
          <>
            <SubmitButton
              isPending={isPending}
              variant="outline"
              className="bg-inherit"
              name="intent"
              value="update-env-variable"
            >
              {isPending ? (
                <>
                  <LoaderIcon className="animate-spin" size={15} />
                  <span className="sr-only">Updating variable value...</span>
                </>
              ) : (
                <>
                  <CheckIcon size={15} className="flex-none" />
                  <span className="sr-only">Update variable value</span>
                </>
              )}
            </SubmitButton>
            <Button
              onClick={() => {
                quitEditMode?.();
              }}
              variant="outline"
              className="bg-inherit"
              type="button"
            >
              <XIcon size={15} className="flex-none" />
              <span className="sr-only">Cancel</span>
            </Button>
          </>
        )}
      </div>
    </fetcher.Form>
  );
}
