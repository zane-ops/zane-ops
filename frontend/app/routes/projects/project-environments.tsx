import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  ChevronRightIcon,
  ExternalLinkIcon,
  LoaderIcon,
  LockKeyholeIcon,
  NetworkIcon,
  PlusIcon
} from "lucide-react";
import * as React from "react";
import { Link, href, redirect, useFetcher } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import type { Project } from "~/api/types";
import { Code } from "~/components/code";
import { StatusBadge } from "~/components/status-badge";
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
import { Separator } from "~/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "~/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import {
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
import { formattedDate, getCsrfTokenHeader, metaTitle } from "~/utils";
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
    "2": { loaderData }
  },
  params
}: Route.ComponentProps) {
  const { data: project } = useQuery({
    ...projectQueries.single(params.projectSlug),
    initialData: loaderData.project
  });
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
        <EnvironmentList
          environments={project.environments}
          projectSlug={params.projectSlug}
        />
      </div>
    </section>
  );
}

type EnvironmentListProps = {
  environments: Project["environments"];
  projectSlug: string;
};
function EnvironmentList({ environments, projectSlug }: EnvironmentListProps) {
  return (
    <div className="grid gap-6 w-full">
      <section>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="sticky top-0 z-20">Name</TableHead>
              <TableHead className="sticky top-0 z-20">Status</TableHead>
              <TableHead className="sticky top-0 z-20">Created at </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {environments.map((env) => (
              <TableRow key={env.id}>
                <TableCell className="p-2">
                  <Link
                    to={href("/project/:projectSlug/:envSlug", {
                      projectSlug,
                      envSlug: env.name
                    })}
                    className="hover:underline flex gap-2 items-center"
                  >
                    <NetworkIcon size={16} className="flex-none text-grey" />
                    <span className="inline-flex gap-1 items-center">
                      {env.name}
                      <ChevronRightIcon size={14} className="text-grey" />
                    </span>
                  </Link>
                </TableCell>
                <TableCell className="p-2">
                  {env.is_preview && (
                    <StatusBadge color="blue" pingState="hidden">
                      Preview
                    </StatusBadge>
                  )}
                  {env.name === "production" && (
                    <TooltipProvider>
                      <Tooltip delayDuration={0}>
                        <TooltipTrigger>
                          <StatusBadge color="gray" pingState="hidden">
                            Locked{" "}
                            <LockKeyholeIcon
                              className="flex-none text-grey"
                              size={16}
                            />
                          </StatusBadge>
                        </TooltipTrigger>

                        <TooltipContent>
                          This environment cannot be deleted or renamed
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  )}
                  {!env.is_preview && env.name !== "production" && (
                    <Code>n/a</Code>
                  )}
                </TableCell>
                <TableCell className="text-grey p-2">
                  {formattedDate(env.created_at)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </section>
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
      return createEnvironment(params.projectSlug, formData);
    }
    case "clone_environment": {
      const clone_from = formData.get("clone_from")?.toString()!;
      return cloneEnvironment(params.projectSlug, clone_from, formData);
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

  if (!cloned_environment.trim()) {
    return {
      errors: {
        type: "validation_error",
        errors: [
          {
            code: "required",
            detail: "Please select one base environment",
            attr: "clone_from"
          }
        ]
      } satisfies ErrorResponseFromAPI,
      userData
    };
  }

  const { error, data } = await apiClient.POST(
    "/api/projects/{slug}/clone-environment/{env_slug}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          slug: project_slug,
          env_slug: cloned_environment.trim()
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

function CreateEnvironmentFormDialog({
  environments
}: { environments: Project["environments"] }) {
  const [isOpen, setIsOpen] = React.useState(false);
  const fetcher = useFetcher<typeof clientAction>();
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const cloneBaseEnvSelectTriggerRef =
    React.useRef<React.ComponentRef<typeof SelectTrigger>>(null);

  const [data, setData] = React.useState(fetcher.data);
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(data?.errors);

  const [intent, setIntent] = React.useState<
    "create_environment" | "clone_environment"
  >("create_environment");

  React.useEffect(() => {
    setData(fetcher.data);

    // only focus on the correct input in case of error
    if (fetcher.state === "idle" && fetcher.data) {
      if (fetcher.data.errors) {
        const errors = getFormErrorsFromResponseData(fetcher.data.errors);
        const key = Object.keys(errors ?? {})[0];
        if (key === "clone_from") {
          cloneBaseEnvSelectTriggerRef.current?.focus();
          return;
        }

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
          setIntent("create_environment");
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
            <FieldSetInput placeholder="ex: staging" />
          </FieldSet>

          <FieldSet
            name="clone_environment"
            className="flex-1 inline-flex gap-2 flex-col"
          >
            <div className="inline-flex gap-2 items-start">
              <FieldSetCheckbox
                checked={intent === "clone_environment"}
                onCheckedChange={() =>
                  setIntent((prev) =>
                    prev === "clone_environment"
                      ? "create_environment"
                      : "clone_environment"
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

          {intent === "clone_environment" && (
            <>
              <hr className="border-border border-dashed" />
              <FieldSet
                name="clone_from"
                errors={errors.clone_from}
                className="flex flex-col gap-2 flex-1"
              >
                <FieldSetLabel htmlFor="clone_from">
                  Source environment
                </FieldSetLabel>

                <FieldSetSelect name="clone_from">
                  <SelectTrigger
                    id="clone_from"
                    ref={cloneBaseEnvSelectTriggerRef}
                  >
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
                errors={errors.deploy_after_clone}
                className="flex-1 inline-flex gap-2 flex-col"
              >
                <div className="inline-flex gap-2 items-start">
                  <FieldSetCheckbox
                    name="deploy_after_clone"
                    className="relative top-1"
                  />

                  <div className="flex flex-col gap-1">
                    <FieldSetLabel>Deploy Resources ?</FieldSetLabel>
                    <small className="text-grey">
                      If checked, this will automatically issue a deploy for
                      each cloned service and compose stack in the new
                      environment
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
              value={intent}
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
