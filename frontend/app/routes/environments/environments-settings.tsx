import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  CheckIcon,
  ExternalLinkIcon,
  FlameIcon,
  FlaskConicalIcon,
  GitPullRequestArrowIcon,
  GithubIcon,
  GitlabIcon,
  InfoIcon,
  LoaderIcon,
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
  FieldSetLabel
} from "~/components/ui/fieldset";
import { HidableInput } from "~/components/ui/hidable-input";
import { Input } from "~/components/ui/input";
import {
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
import { getCsrfTokenHeader } from "~/utils";
import type { Route } from "./+types/environments-settings";

export default function EnvironmentSettingsPage({
  params,
  matches: {
    "2": { loaderData }
  }
}: Route.ComponentProps) {
  const { data: env } = useQuery({
    ...environmentQueries.single(params.projectSlug, params.envSlug),
    initialData: loaderData.environment
  });

  const [isPasswordShown, setIsPasswordShown] = React.useState(false);

  const preview_head_repo_path = env.preview_metadata?.head_repository_url
    ? new URL(env.preview_metadata?.head_repository_url).pathname.substring(1)
    : null;
  const preview_base_repo_path = env.preview_metadata?.pr_base_repo_url
    ? new URL(env.preview_metadata?.pr_base_repo_url).pathname.substring(1)
    : null;

  return (
    <section className="py-8 flex flex-col gap-4">
      <div className="grid lg:grid-cols-12 gap-10 relative">
        <div className="lg:col-span-10 flex flex-col">
          <section id="details" className="flex gap-1 scroll-mt-20">
            <div className="w-16 hidden md:flex flex-col items-center">
              <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
                <InfoIcon size={15} className="flex-none text-grey" />
              </div>
              <div className="h-full border border-grey/50"></div>
              {env.name === "production" && (
                <div className="bg-grey/50 rounded-md size-2" />
              )}
            </div>
            <div
              className={cn(
                "w-full flex flex-col gap-5 pt-1",
                env.name === "production" ? "pb-6" : "pb-8"
              )}
            >
              <h2 className="text-lg text-grey">Details</h2>

              <EnvironmentNameForm environment={env} />
            </div>
          </section>

          {env.preview_metadata && (
            <section id="metadata" className="flex gap-1 scroll-mt-20">
              <div className="w-16 hidden md:flex flex-col items-center">
                <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
                  <FlaskConicalIcon size={15} className="flex-none text-grey" />
                </div>
                <div className="h-full border border-grey/50"></div>
              </div>
              <div className="w-full flex flex-col gap-5 pt-1 pb-8">
                <h2 className="text-lg text-grey">Preview metadata</h2>

                {env.is_preview && env.preview_metadata && (
                  <div className="flex flex-col gap-5">
                    <div className="flex flex-col gap-2">
                      <div className="w-full flex flex-col gap-2">
                        <label
                          className="text-muted-foreground"
                          htmlFor="preview_source_trigger"
                        >
                          Triggered By
                        </label>
                        <div className="flex flex-col gap-1 relative">
                          <Input
                            disabled
                            id="preview_source_trigger"
                            defaultValue={
                              env.preview_metadata.source_trigger === "API"
                                ? "API"
                                : "Pull Request"
                            }
                            className={cn(
                              "disabled:placeholder-shown:font-mono disabled:bg-muted",
                              "disabled:border-transparent disabled:opacity-100 disabled:select-none",
                              "text-transparent"
                            )}
                          />
                          <div className="absolute inset-y-0 px-3 text-sm flex items-center gap-1.5">
                            <span>
                              {env.preview_metadata.source_trigger === "API"
                                ? "API"
                                : "Pull Request"}
                            </span>
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

                      {env.preview_metadata.pr_title && (
                        <div className="w-full flex flex-col gap-2">
                          <label
                            className="text-muted-foreground"
                            htmlFor="pr_title"
                          >
                            Pull Request title
                          </label>
                          <div className="flex flex-col gap-1 relative">
                            <Input
                              disabled
                              id="pr_title"
                              defaultValue={`${env.preview_metadata.pr_title} (#${env.preview_metadata.pr_number})`}
                              className={cn(
                                "disabled:placeholder-shown:font-mono disabled:bg-muted",
                                "disabled:border-transparent disabled:opacity-100 disabled:select-none"
                              )}
                            />
                          </div>
                        </div>
                      )}
                      {env.preview_metadata.pr_author && (
                        <div className="w-full flex flex-col gap-2">
                          <label
                            className="text-muted-foreground"
                            htmlFor="pr_title"
                          >
                            Pull Request author
                          </label>
                          <div className="flex flex-col gap-1 relative">
                            <Input
                              disabled
                              id="pr_author"
                              defaultValue={`${env.preview_metadata.pr_author}`}
                              className={cn(
                                "disabled:placeholder-shown:font-mono disabled:bg-muted",
                                "disabled:border-transparent disabled:opacity-100 disabled:select-none"
                              )}
                            />
                          </div>
                        </div>
                      )}

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
                            <ExternalLinkIcon size={15} className="flex-none" />
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
                          Head Repository
                        </label>
                        <div className="flex flex-col gap-1 relative">
                          <Input
                            disabled
                            id="external_url"
                            defaultValue={preview_head_repo_path}
                            className={cn(
                              "disabled:placeholder-shown:font-mono disabled:bg-muted",
                              "disabled:border-transparent disabled:opacity-100 disabled:select-none",
                              "text-transparent"
                            )}
                          />
                          <div className="absolute inset-y-0 px-3 text-sm flex items-center gap-1.5">
                            <span>{preview_head_repo_path}</span>
                          </div>
                        </div>
                      </div>

                      <div className="grid md:grid-cols-2 gap-2">
                        <div
                          className={cn(
                            "w-full flex flex-col gap-2",
                            env.preview_metadata.source_trigger ===
                              "PULL_REQUEST" && "col-span-full"
                          )}
                        >
                          <label
                            className="text-muted-foreground"
                            htmlFor="external_url"
                          >
                            Head Branch name
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

                        {env.preview_metadata.source_trigger === "API" && (
                          <div className={cn("w-full flex flex-col gap-2")}>
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
                                <span>{env.preview_metadata.commit_sha}</span>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>

                      {env.preview_metadata.source_trigger ===
                        "PULL_REQUEST" && (
                        <>
                          <hr className="h-px border border-border border-dashed my-2" />
                          <div className="w-full flex flex-col gap-2">
                            <label
                              className="text-muted-foreground"
                              htmlFor="external_url"
                            >
                              Base Repository
                            </label>
                            <div className="flex flex-col gap-1 relative">
                              <Input
                                disabled
                                id="external_url"
                                defaultValue={preview_base_repo_path}
                                className={cn(
                                  "disabled:placeholder-shown:font-mono disabled:bg-muted",
                                  "disabled:border-transparent disabled:opacity-100 disabled:select-none",
                                  "text-transparent"
                                )}
                              />
                              <div className="absolute inset-y-0 px-3 text-sm flex items-center gap-1.5">
                                <span>{preview_base_repo_path}</span>
                              </div>
                            </div>
                          </div>

                          <div className="grid gap-2">
                            <div className={cn("w-full flex flex-col gap-2")}>
                              <label
                                className="text-muted-foreground"
                                htmlFor="external_url"
                              >
                                Base Branch name
                              </label>
                              <div className="flex flex-col gap-1 relative">
                                <Input
                                  disabled
                                  id="external_url"
                                  defaultValue={
                                    env.preview_metadata.pr_base_branch_name
                                  }
                                  className={cn(
                                    "disabled:placeholder-shown:font-mono disabled:bg-muted",
                                    "disabled:border-transparent disabled:opacity-100 disabled:select-none",
                                    "text-transparent"
                                  )}
                                />
                                <div className="absolute inset-y-0 px-3 text-sm flex items-center gap-1.5">
                                  <span>
                                    {env.preview_metadata.pr_base_branch_name}
                                  </span>
                                </div>
                              </div>
                            </div>
                          </div>
                        </>
                      )}
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

                        <HidableInput
                          disabled
                          type={isPasswordShown ? "text" : "password"}
                          defaultValue={env.preview_metadata.auth_password}
                          name="credentials.password"
                          id="credentials.password"
                          className={cn(
                            "disabled:placeholder-shown:font-mono disabled:bg-muted ",
                            "disabled:border-transparent disabled:opacity-100"
                          )}
                        />
                      </fieldset>
                    )}
                  </div>
                )}
              </div>
            </section>
          )}

          {env.name !== "production" && (
            <section id="danger" className="flex gap-1 scroll-mt-20">
              <div className="w-16 hidden md:flex flex-col items-center">
                <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-red-500">
                  <FlameIcon size={15} className="flex-none text-red-500" />
                </div>
              </div>
              <div className="w-full flex flex-col gap-5 pt-1 pb-14">
                <h2 className="text-lg text-red-400">Danger Zone</h2>
                <div className="flex flex-col gap-4 items-start max-w-4xl w-full rounded-md border border-border p-4">
                  <div className="flex md:flex-row gap-4 justify-between items-center w-full">
                    <div className="flex flex-col gap-1">
                      <h3 className="text-lg font-medium">
                        Delete environment
                      </h3>
                      <p>
                        Deletes this environment along with all its services
                      </p>
                    </div>
                    {env.name !== "production" && (
                      <EnvironmentDeleteFormDialog environment={env.name} />
                    )}
                  </div>
                </div>
              </div>
            </section>
          )}
        </div>
      </div>
    </section>
  );
}

function EnvironmentNameForm({
  environment: env
}: {
  environment: Route.ComponentProps["matches"][2]["loaderData"]["environment"];
}) {
  const isModifiable = !env.is_preview && env.name !== "production";
  const fetcher = useFetcher<typeof clientAction>();

  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  return (
    <fetcher.Form method="POST" className="flex flex-col gap-4">
      {errors.non_field_errors && (
        <Alert variant="destructive">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errors.non_field_errors}</AlertDescription>
        </Alert>
      )}

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

      <div className="flex  items-center gap-2 pt-4 px-4 -mx-4">
        <SubmitButton
          variant="secondary"
          isPending={fetcher.state !== "idle"}
          className="inline-flex gap-1"
          name="intent"
          value="rename_environment"
          disabled={!isModifiable}
        >
          {fetcher.state !== "idle" ? (
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
      </div>
    </fetcher.Form>
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
      return renameEnvironment(params.projectSlug, params.envSlug, formData);
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

async function renameEnvironment(
  project_slug: string,
  env_slug: string,
  formData: FormData
) {
  const userData = {
    name: formData.get("name")?.toString() ?? ""
  };

  const { error, data } = await apiClient.PATCH(
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

  if (data.name !== env_slug) {
    await Promise.all([
      queryClient.invalidateQueries(projectQueries.single(project_slug)),
      queryClient.invalidateQueries(
        environmentQueries.serviceList(project_slug, env_slug)
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
    href("/project/:projectSlug/:envSlug", {
      projectSlug: project_slug,
      envSlug: "production"
    })
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
          <span>Delete this environment</span>
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
