import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  ExternalLinkIcon,
  LayoutListIcon,
  LoaderIcon,
  PencilLineIcon,
  PlusIcon,
  Trash2Icon
} from "lucide-react";
import { Link, useFetcher, useSearchParams } from "react-router";
import { Pagination } from "~/components/pagination";
import { StatusBadge } from "~/components/status-badge";
import { Button, SubmitButton } from "~/components/ui/button";
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
  type BuildRegistry,
  buildRegistryListFilters,
  buildRegistryQueries
} from "~/lib/queries";
import { queryClient } from "~/root";
import { formatURL, metaTitle } from "~/utils";
import type { Route } from "./+types/build-registry-list";

import React from "react";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "~/components/ui/dialog";
import { cn } from "~/lib/utils";

export function meta() {
  return [
    metaTitle("Build Registries")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const searchParams = new URL(request.url).searchParams;
  const search = buildRegistryListFilters.parse(searchParams);

  const filters = {
    page: search.page ?? 1,
    per_page: search.per_page ?? 10
  };

  const registryList = await queryClient.ensureQueryData(
    buildRegistryQueries.list(filters)
  );
  return {
    registryList
  };
}

export default function BuildRegistryListPage({
  loaderData
}: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const search = buildRegistryListFilters.parse(searchParams);

  const filters = {
    page: search.page ?? 1,
    per_page: search.per_page ?? 10
  };

  const {
    data: { results: registries, count: totalDeployments }
  } = useQuery({
    ...buildRegistryQueries.list(filters),
    initialData: loaderData.registryList
  });

  const totalPages = Math.ceil(totalDeployments / filters.per_page);

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Build Registries</h2>
        <Button asChild variant="secondary" className="flex gap-2">
          <Link to="new" prefetch="intent">
            New <PlusIcon size={18} />
          </Link>
        </Button>
      </div>
      <Separator />
      <h3>
        Manage registries used by ZaneOps to store your built applications.
      </h3>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="sticky top-0 z-20">Name</TableHead>
            <TableHead className="sticky top-0 z-20">Username</TableHead>
            <TableHead className="sticky top-0 z-20">Domain</TableHead>
            <TableHead className="sticky top-0 z-20 px-4">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {registries.length === 0 && (
            <TableRow className="px-2">
              <TableCell
                className="p-2 text-muted-foreground italic"
                colSpan={4}
              >
                -- No registries found --
              </TableCell>
            </TableRow>
          )}

          {registries.map((registry) => (
            <TableRow key={registry.id}>
              <TableCell className="p-2">
                <div className="flex gap-2 items-center">
                  {registry.name}
                  {registry.is_default && (
                    <StatusBadge color="blue" pingState="hidden">
                      Default
                    </StatusBadge>
                  )}
                </div>
              </TableCell>
              <TableCell className="p-2">
                {registry.registry_username}
              </TableCell>
              <TableCell className="p-2">
                <a
                  href={`${registry.is_secure ? "https" : "http"}://${registry.registry_domain}`}
                  target="_blank"
                  className="underline text-link inline-flex items-center gap-1"
                  rel="noreferrer"
                >
                  <span>{`${registry.is_secure ? "https" : "http"}://${registry.registry_domain}`}</span>
                  <ExternalLinkIcon size={16} className="flex-none" />
                </a>
              </TableCell>

              <TableCell className="p-2">
                <div className="flex items-center gap-2">
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger asChild>
                        <Button variant="ghost" asChild size="sm">
                          <Link
                            to={`./${registry.id}`}
                            className="inline-flex gap-2 items-center"
                          >
                            <PencilLineIcon className="size-4 flex-none" />
                            <span className="sr-only">Edit Registry</span>
                          </Link>
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Edit Registry</TooltipContent>
                    </Tooltip>

                    <Separator className="h-2 relative top-0.5 w-px bg-grey rounded-md" />

                    <Tooltip delayDuration={0}>
                      <TooltipTrigger asChild>
                        <Button variant="ghost" asChild size="sm">
                          <Link
                            to={`./${registry.id}/list-images`}
                            className="inline-flex gap-2 items-center"
                          >
                            <LayoutListIcon className="size-4 flex-none" />
                            <span className="sr-only">
                              List Images in Registry
                            </span>
                          </Link>
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>List Images in Registry</TooltipContent>
                    </Tooltip>

                    <Separator className="h-2 relative top-0.5 w-px bg-grey rounded-md" />
                  </TooltipProvider>

                  <DeleteConfirmationFormDialog registry={registry} />
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <div className="my-4 block">
        {registries.length > 0 && totalDeployments > 10 && (
          <Pagination
            totalPages={totalPages}
            currentPage={filters.page}
            perPage={filters.per_page}
            onChangePage={(newPage) => {
              searchParams.set("page", newPage.toString());
              setSearchParams(searchParams, {
                replace: true
              });
            }}
            onChangePerPage={(newPerPage) => {
              searchParams.set("page", "1");
              searchParams.set("per_page", newPerPage.toString());
              setSearchParams(searchParams, {
                replace: true
              });
            }}
          />
        )}
      </div>
    </section>
  );
}

function DeleteConfirmationFormDialog({
  registry
}: { registry: BuildRegistry }) {
  const [isOpen, setIsOpen] = React.useState(false);
  const fetcher = useFetcher();

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
              <Button
                variant="ghost"
                className="text-red-400 inline-flex gap-2 items-center disabled:opacity-50"
                size="sm"
                disabled={registry.is_default}
              >
                <Trash2Icon className="size-4 flex-none" />
                <span className="sr-only">Delete Registry</span>
              </Button>
            </DialogTrigger>
          </TooltipTrigger>
          <TooltipContent>Delete Registry</TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <DialogContent className="gap-0">
        <DialogHeader>
          <DialogTitle>Delete this Build Registry ?</DialogTitle>

          <Alert variant="danger" className="my-5">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Warning</AlertTitle>
            <AlertDescription>
              This action <strong>CANNOT be undone</strong>. Deleting this
              registry will permanently remove all stored container images.
            </AlertDescription>
          </Alert>
        </DialogHeader>

        <DialogFooter className="-mx-6 px-6">
          <fetcher.Form
            method="post"
            action={`./${registry.id}`}
            className="flex items-center gap-4 w-full"
          >
            <input type="hidden" name="intent" value="delete" />
            <input type="hidden" name="name" value={registry.name} />
            <input
              type="hidden"
              name="domain"
              value={registry.registry_domain}
            />
            <input
              type="hidden"
              name="scheme"
              value={registry.is_secure ? "https" : "http"}
            />

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
