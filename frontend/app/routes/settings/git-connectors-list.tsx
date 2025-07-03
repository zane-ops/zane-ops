import { prefix } from "@react-router/dev/routes";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  ArrowBigDownDashIcon,
  CheckIcon,
  ChevronDownIcon,
  ClockIcon,
  ExternalLinkIcon,
  GithubIcon,
  GitlabIcon,
  LoaderIcon,
  PenLineIcon,
  PencilIcon,
  Trash2Icon,
  UnplugIcon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { flushSync } from "react-dom";
import {
  Form,
  href,
  useFetcher,
  useNavigate,
  useSearchParams
} from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import { Pagination } from "~/components/pagination";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Badge } from "~/components/ui/badge";
import { Button, SubmitButton } from "~/components/ui/button";
import { Card, CardContent } from "~/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "~/components/ui/dialog";
import { FieldSet, FieldSetInput } from "~/components/ui/fieldset";
import { Input } from "~/components/ui/input";
import {
  Menubar,
  MenubarContent,
  MenubarContentItem,
  MenubarMenu,
  MenubarTrigger
} from "~/components/ui/menubar";
import { Separator } from "~/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { type GitApp, gitAppSearchSchema, gitAppsQueries } from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import { queryClient } from "~/root";
import { formattedDate, getCsrfTokenHeader, metaTitle } from "~/utils";
import type { Route } from "./+types/git-connectors-list";

export function meta() {
  return [metaTitle("Git apps")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const searchParams = new URL(request.url).searchParams;

  const search = gitAppSearchSchema.parse(searchParams);
  const { page = 1, per_page = 10 } = search;
  const filters = {
    page,
    per_page
  };

  // fetch the data on first load to prevent showing the loading fallback
  const gitAppList = await queryClient.ensureQueryData(
    gitAppsQueries.list(filters)
  );

  return {
    gitAppList
  };
}

export default function GitConnectorsListPage({
  loaderData
}: Route.ComponentProps) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const search = gitAppSearchSchema.parse(searchParams);
  const { page = 1, per_page = 10 } = search;

  const filters = {
    page,
    per_page
  };

  const gitAppListQuery = useQuery({
    ...gitAppsQueries.list(filters),
    initialData: loaderData.gitAppList
  });

  const gitAppList = gitAppListQuery.data;
  const totalCount = gitAppList.count;
  const totalPages = Math.ceil(totalCount / per_page);
  const emptySearchParams =
    !searchParams.get("per_page") && !searchParams.get("page");

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Git apps</h2>
        <Menubar className="border-none w-fit">
          <MenubarMenu>
            <MenubarTrigger asChild>
              <Button variant="secondary" className="flex gap-2">
                Create <ChevronDownIcon size={18} />
              </Button>
            </MenubarTrigger>
            <MenubarContent
              align="center"
              alignOffset={0}
              className="border min-w-0 mx-9  border-border"
            >
              <MenubarContentItem
                icon={GithubIcon}
                text="GitHub app"
                onClick={() => {
                  navigate(href("/settings/git-connectors/create-github-app"));
                }}
              />

              <MenubarContentItem
                icon={GitlabIcon}
                text="gitlab app"
                disabled
                // onClick={() => {
                //   navigate("/settings");
                // }}
              />
            </MenubarContent>
          </MenubarMenu>
        </Menubar>
      </div>
      <Separator />
      <h3>
        Connect your Git provider to deploy private repositories, auto-deploy on
        commit as well as create pull request preview environments.
      </h3>

      <ul className="flex flex-col gap-2">
        {totalCount === 0 && (
          <div className="border-border border-dashed border-1 flex items-center justify-center px-6 py-10 text-grey">
            No connector found
          </div>
        )}

        {gitAppList.results.map((git_app) => (
          <li key={git_app.id}>
            {git_app.github && (
              <GithubAppCard app={git_app.github} parent_id={git_app.id} />
            )}
          </li>
        ))}
      </ul>

      <div
        className={cn("my-4 block", {
          "opacity-40 pointer-events-none": gitAppListQuery.isFetching
        })}
      >
        {!emptySearchParams && totalCount > 10 && (
          <Pagination
            totalPages={totalPages}
            currentPage={page}
            perPage={per_page}
            onChangePage={(newPage) => {
              searchParams.set(`page`, newPage.toString());
              setSearchParams(searchParams, { replace: true });
            }}
            onChangePerPage={(newPerPage) => {
              searchParams.set(`per_page`, newPerPage.toString());
              searchParams.set(`page`, "1");
              setSearchParams(searchParams, { replace: true });
            }}
          />
        )}
      </div>
    </section>
  );
}

type GithubAppCardProps = {
  app: NonNullable<GitApp["github"]>;
  parent_id: string;
};

function GithubAppCard({ app, parent_id }: GithubAppCardProps) {
  const testConnectionFetcher = useFetcher<typeof clientAction>();
  const renameFetcher = useFetcher<typeof clientAction>();
  const isRenaming = renameFetcher.state !== "idle";
  const [isEditing, setIsEditing] = React.useState(false);
  const [data, setData] = React.useState(renameFetcher.data);
  const errors = getFormErrorsFromResponseData(data?.errors);
  const inputRef = React.useRef<React.ComponentRef<"input">>(null);

  React.useEffect(() => {
    setData(renameFetcher.data);

    if (renameFetcher.state === "idle" && renameFetcher.data?.data) {
      setIsEditing(false);
    }
  }, [renameFetcher.state, renameFetcher.data]);

  return (
    <Card>
      <CardContent className="rounded-md p-4 gap-4 flex flex-col items-start md:flex-row md:items-center bg-toggle">
        <div>
          <div className=" flex-col gap-2 items-center text-grey hidden md:flex">
            <GithubIcon size={30} className="flex-none" />
            <Badge variant="outline" className="text-grey">
              app
            </Badge>
          </div>
        </div>
        <div className="flex flex-col flex-1 gap-0.5">
          <renameFetcher.Form
            className="flex items-start group gap-2"
            method="post"
          >
            <input type="hidden" name="intent" value="rename_github_app" />
            <input type="hidden" name="id" value={app.id} />
            {isEditing ? (
              <>
                <FieldSet name="name" errors={errors.name}>
                  <FieldSetInput
                    ref={inputRef}
                    placeholder="github app name"
                    defaultValue={app.name}
                  />
                </FieldSet>
                <SubmitButton
                  isPending={isRenaming}
                  variant="outline"
                  className="bg-inherit"
                  name="intent"
                  value="update-slug"
                  size="sm"
                >
                  {isRenaming ? (
                    <>
                      <LoaderIcon className="animate-spin" size={15} />
                      <span className="sr-only">Submiting...</span>
                    </>
                  ) : (
                    <>
                      <CheckIcon size={15} className="flex-none" />
                      <span className="sr-only">Submit</span>
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
                  size="sm"
                >
                  <XIcon size={15} className="flex-none" />
                  <span className="sr-only">Cancel</span>
                </Button>
              </>
            ) : (
              <>
                <h3 className="text-lg font-medium">{app.name}</h3>
                <Button
                  type="button"
                  className="opacity-100 md:opacity-0 focus:opacity-100 group-hover:opacity-100"
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    flushSync(() => setIsEditing(true));
                    inputRef.current?.focus();
                  }}
                >
                  <PenLineIcon size={15} className="flex-none" />
                  <span className="sr-only">Rename app</span>
                </Button>
              </>
            )}
          </renameFetcher.Form>
          <div className="text-sm text-link flex items-center gap-1">
            <ExternalLinkIcon size={15} className="flex-none" />
            <a href={app.app_url} className="break-all" target="_blank">
              {app.app_url}
            </a>
          </div>
          <div className="text-grey text-sm flex items-center gap-1">
            <ClockIcon size={15} className="flex-none" />
            <span>
              Added on&nbsp;
              <time dateTime={app.created_at}>
                {formattedDate(app.created_at)}
              </time>
            </span>
          </div>
        </div>
        <testConnectionFetcher.Form
          id={`test-connection-${app.id}`}
          className="hidden"
          method="post"
        >
          <input type="hidden" name="id" value={app.id} />
        </testConnectionFetcher.Form>
        <div className="flex items-center gap-1">
          <TooltipProvider>
            {!app.is_installed ? (
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button size="sm" variant="ghost" asChild>
                    <Button asChild variant="ghost">
                      <a
                        href={`${app.app_url}/installations/new?state=install:${app.id}`}
                      >
                        <ArrowBigDownDashIcon size={15} />
                        <span className="sr-only">
                          Install application on GitHub
                        </span>
                      </a>
                    </Button>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Install application on GitHub</TooltipContent>
              </Tooltip>
            ) : (
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <SubmitButton
                    isPending={testConnectionFetcher.state !== "idle"}
                    form={`test-connection-${app.id}`}
                    size="sm"
                    variant="ghost"
                    name="intent"
                    value="test_github_app_connection"
                  >
                    {testConnectionFetcher.state !== "idle" ? (
                      <>
                        <LoaderIcon className="animate-spin" size={15} />
                        <span className="sr-only">Testing...</span>
                      </>
                    ) : (
                      <>
                        <UnplugIcon size={15} />
                        <span className="sr-only">
                          Test GitHub App installation
                        </span>
                      </>
                    )}
                  </SubmitButton>
                </TooltipTrigger>
                <TooltipContent>Test GitHub App installation</TooltipContent>
              </Tooltip>
            )}
          </TooltipProvider>
          <DeleteConfirmationFormDialog git_app_id={parent_id} type="github" />
        </div>
      </CardContent>
    </Card>
  );
}

function DeleteConfirmationFormDialog({
  git_app_id,
  type
}: { git_app_id: string; type: "github" | "gitlab" }) {
  const [isOpen, setIsOpen] = React.useState(false);
  const fetcher = useFetcher<typeof clientAction>();

  const isPending = fetcher.state !== "idle";

  React.useEffect(() => {
    // only focus on the correct input in case of error
    if (fetcher.state === "idle" && fetcher.data && !fetcher.data.errors) {
      setIsOpen(false);
    }
  }, [fetcher.state, fetcher.data]);

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <TooltipProvider>
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <DialogTrigger asChild>
              <Button size="sm" variant="ghost">
                <Trash2Icon className="text-red-400" size={15} />
                <span className="sr-only">Delete application</span>
              </Button>
            </DialogTrigger>
          </TooltipTrigger>
          <TooltipContent>Delete application</TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <DialogContent className="gap-0">
        <DialogHeader>
          <DialogTitle>Delete this Git application ?</DialogTitle>

          <Alert variant="destructive" className="my-5">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Warning</AlertTitle>
            <AlertDescription>
              This action <strong>CANNOT</strong> be undone. This will
              permanently delete the git app in ZaneOps. This will not delete
              the app in {type === "github" ? "GitHub" : "Gitlab"}.
            </AlertDescription>
          </Alert>
        </DialogHeader>

        <DialogFooter className="-mx-6 px-6">
          <fetcher.Form
            method="post"
            className="flex items-center gap-4 w-full"
          >
            <input type="hidden" name="id" value={git_app_id} />
            <input type="hidden" name="intent" value="delete_git_app" />

            <SubmitButton
              isPending={isPending}
              variant="destructive"
              className={cn(
                "inline-flex gap-1 items-center",
                isPending ? "bg-red-400" : "bg-red-500"
              )}
            >
              {isPending ? (
                <>
                  <LoaderIcon className="animate-spin flex-none" size={15} />
                  <span>Submitting...</span>
                </>
              ) : (
                <>
                  <span>Confirm</span>
                </>
              )}
            </SubmitButton>

            <Button
              variant="outline"
              type="button"
              onClick={() => setIsOpen(false)}
            >
              Cancel
            </Button>
          </fetcher.Form>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const formData = await request.formData();

  const intent = formData.get("intent")?.toString();

  switch (intent) {
    case "test_github_app_connection": {
      return testGithubAppConnection(formData);
    }
    case "delete_git_app": {
      return deleteGitApp(formData);
    }
    case "rename_github_app": {
      return renameGithubApp(formData);
    }
    default: {
      throw new Error("Unexpected intent");
    }
  }
}

async function deleteGitApp(formData: FormData) {
  const { data, error } = await apiClient.DELETE(
    "/api/connectors/delete/{id}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          id: formData.get("id")?.toString()!
        }
      }
    }
  );
  if (error) {
    const fullErrorMessage = error.errors.map((err) => err.detail).join(" ");

    toast.error("Error", {
      description: fullErrorMessage,
      closeButton: true
    });
    return { errors: error };
  }

  toast.success("Success", {
    description: `Git app deleted succesfully`,
    closeButton: true
  });

  await queryClient.invalidateQueries({
    predicate(query) {
      const prefix = gitAppsQueries.list().queryKey[0];
      return query.queryKey.includes(prefix);
    }
  });

  return { data };
}

async function testGithubAppConnection(formData: FormData) {
  const { data, error } = await apiClient.GET(
    "/api/connectors/github/{id}/repositories/",
    {
      params: {
        path: {
          id: formData.get("id")?.toString()!
        }
      }
    }
  );

  if (error) {
    const fullErrorMessage = error.errors.map((err) => err.detail).join(" ");

    toast.error("Error", {
      description: fullErrorMessage,
      closeButton: true
    });
    return { errors: error };
  }

  toast.success("Success", {
    description: `Found ${data.count} repositories`,
    closeButton: true
  });

  return { data };
}

async function renameGithubApp(formData: FormData) {
  const userData = {
    name: formData.get("name")?.toString()
  } satisfies RequestInput<"patch", "/api/connectors/github/{id}/rename/">;

  const { data, error } = await apiClient.PATCH(
    "/api/connectors/github/{id}/rename/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          id: formData.get("id")?.toString()!
        }
      },
      body: userData
    }
  );

  if (error) {
    const fullErrorMessage = error.errors.map((err) => err.detail).join(" ");

    toast.error("Error", {
      description: fullErrorMessage,
      closeButton: true
    });
    return { errors: error };
  }

  await queryClient.invalidateQueries({
    predicate(query) {
      const prefix = gitAppsQueries.list().queryKey[0];
      return query.queryKey.includes(prefix);
    }
  });
  return { data };
}
