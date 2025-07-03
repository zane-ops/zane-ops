import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  ChevronDownIcon,
  GithubIcon,
  GitlabIcon,
  LoaderIcon,
  Trash2Icon
} from "lucide-react";
import * as React from "react";
import { href, useFetcher, useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { GithubAppCard } from "~/components/github-app-card";
import { Pagination } from "~/components/pagination";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "~/components/ui/dialog";
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
import { gitAppSearchSchema, gitAppsQueries } from "~/lib/queries";
import { cn } from "~/lib/utils";
import { queryClient } from "~/root";
import { getCsrfTokenHeader, metaTitle } from "~/utils";
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
              <GithubAppCard app={git_app.github}>
                <DeleteConfirmationFormDialog
                  git_app_id={git_app.id}
                  type="github"
                />
              </GithubAppCard>
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
