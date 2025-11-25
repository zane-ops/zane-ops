import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  ExternalLinkIcon,
  LoaderIcon,
  PencilLineIcon,
  PlusIcon,
  Trash2Icon,
  ZapIcon
} from "lucide-react";
import { Link, useFetcher } from "react-router";
import { StatusBadge } from "~/components/status-badge";
import { Button, SubmitButton } from "~/components/ui/button";

import * as React from "react";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "~/components/ui/dialog";
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
import { DEFAULT_REGISTRIES } from "~/lib/constants";
import {
  type SharedRegistryCredentials,
  sharedRegistryCredentialsQueries
} from "~/lib/queries";
import { cn } from "~/lib/utils";
import { queryClient } from "~/root";
import { metaTitle } from "~/utils";
import type { Route } from "./+types/registry-credentials-list";

export function meta() {
  return [
    metaTitle("Registry Credentials")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader() {
  const credentials = await queryClient.ensureQueryData(
    sharedRegistryCredentialsQueries.list
  );
  return { credentials };
}

export default function ContainerRegistryCredentialsPage({
  loaderData
}: Route.ComponentProps) {
  const { data: credentials } = useQuery({
    ...sharedRegistryCredentialsQueries.list,
    initialData: loaderData.credentials
  });

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Shared Container Registry Credentials</h2>
        <Button asChild variant="secondary" className="flex gap-2">
          <Link to="new" prefetch="intent">
            New <PlusIcon size={18} />
          </Link>
        </Button>
      </div>
      <Separator />
      <h3>
        Store external container registry credentials to pull and deploy private
        images.
      </h3>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="sticky top-0 z-20">Type</TableHead>
            <TableHead className="sticky top-0 z-20">Slug</TableHead>
            <TableHead className="sticky top-0 z-20">Username</TableHead>
            <TableHead className="sticky top-0 z-20">URL</TableHead>
            <TableHead className="sticky top-0 z-20 px-4">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {credentials.length === 0 ? (
            <TableRow className="px-2">
              <TableCell
                colSpan={5}
                className="p-2 text-muted-foreground italic"
              >
                -- No Credentials found --
              </TableCell>
            </TableRow>
          ) : (
            credentials.map((credential) => {
              const Icon = DEFAULT_REGISTRIES[credential.registry_type].Icon;
              return (
                <TableRow className="px-2" key={credential.id}>
                  <TableCell className="!px-2 py-2">
                    <StatusBadge
                      color={
                        credential.registry_type === "DOCKER_HUB" ||
                        credential.registry_type === "GOOGLE_ARTIFACT"
                          ? "blue"
                          : credential.registry_type === "AWS_ECR" ||
                              credential.registry_type === "GITLAB"
                            ? "yellow"
                            : "gray"
                      }
                      pingState="hidden"
                      className="capitalize"
                    >
                      <Icon />
                      {DEFAULT_REGISTRIES[credential.registry_type].name}
                    </StatusBadge>
                  </TableCell>
                  <TableCell className="p-2">{credential.slug}</TableCell>
                  <TableCell className="p-2">
                    {credential.username ?? (
                      <span className="text-grey font-mono">N/A</span>
                    )}
                  </TableCell>
                  <TableCell className="p-2">
                    <a
                      href={credential.url}
                      target="_blank"
                      className="underline text-link inline-flex items-center gap-1"
                      rel="noreferrer"
                    >
                      <span>{credential.url}</span>
                      <ExternalLinkIcon size={16} className="flex-none" />
                    </a>
                  </TableCell>
                  <TableCell className="p-2 ">
                    <CredentialActions credentials={credential} />
                  </TableCell>
                </TableRow>
              );
            })
          )}
        </TableBody>
      </Table>
    </section>
  );
}

function CredentialActions({
  credentials
}: { credentials: Omit<SharedRegistryCredentials, "password"> }) {
  const testFetcher = useFetcher();
  return (
    <div className="flex items-center gap-1">
      <testFetcher.Form
        method="post"
        action={`./${credentials.id}`}
        id={`test-${credentials.id}`}
      >
        <input type="hidden" name="intent" value="test" />
        <input
          type="hidden"
          name="username"
          value={credentials.username ?? ""}
        />
        <input type="hidden" name="url" value={credentials.url ?? ""} />
      </testFetcher.Form>
      <TooltipProvider>
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <Button size="sm" variant="ghost" asChild className="gap-1">
              <Link to={`./${credentials.id}`}>
                <span className="sr-only">Edit</span>
                <PencilLineIcon className="flex-none size-4" />
              </Link>
            </Button>
          </TooltipTrigger>
          <TooltipContent>Edit Credentials</TooltipContent>
        </Tooltip>
        <div className="h-2 relative top-0.5 w-px bg-grey rounded-md" />
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <SubmitButton
              form={`test-${credentials.id}`}
              size="sm"
              variant="ghost"
              className="gap-1"
              isPending={testFetcher.state !== "idle"}
            >
              {testFetcher.state !== "idle" ? (
                <>
                  <span className="sr-only">Testing Credentials...</span>
                  <LoaderIcon className="flex-none size-4 animate-spin" />
                </>
              ) : (
                <>
                  <span className="sr-only">Test Credentials</span>
                  <ZapIcon className="flex-none size-4" />
                </>
              )}
            </SubmitButton>
          </TooltipTrigger>
          <TooltipContent>Test Credentials</TooltipContent>
        </Tooltip>
        <div className="h-2 relative top-0.5 w-px bg-grey rounded-md" />
      </TooltipProvider>
      <DeleteConfirmationFormDialog credentials={credentials} />
    </div>
  );
}

function DeleteConfirmationFormDialog({
  credentials
}: { credentials: Omit<SharedRegistryCredentials, "password"> }) {
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
              <Button size="sm" variant="ghost" className="gap-1 text-red-400">
                <>
                  <span className="sr-only">Delete Credentials</span>
                  <Trash2Icon className="flex-none size-4" />
                </>
              </Button>
            </DialogTrigger>
          </TooltipTrigger>
          <TooltipContent>Delete Credentials</TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <DialogContent className="gap-0">
        <DialogHeader>
          <DialogTitle>Delete these Credentials ?</DialogTitle>

          <Alert variant="destructive" className="my-5">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Warning</AlertTitle>
            <AlertDescription>
              This action <strong>CANNOT</strong> be undone. This will
              permanently delete the credentials.
            </AlertDescription>
          </Alert>
        </DialogHeader>

        <dl className="py-2 border-y border-border mb-5 ">
          <div className="flex items-center gap-1">
            <dt className="select-none">Username: </dt>
            <dd className="text-grey dark:text-foreground">
              {credentials.username ?? (
                <span className="text-grey font-mono">N/A</span>
              )}
            </dd>
          </div>
          <div className="flex items-center gap-1">
            <dt className="select-none">URL:</dt>
            <dd className="text-link">
              <a
                href={credentials.url}
                target="_blank"
                className="underline text-link inline-flex items-center gap-1"
                rel="noreferrer"
              >
                <span>{credentials.url}</span>
                <ExternalLinkIcon size={16} className="flex-none" />
              </a>
            </dd>
          </div>
        </dl>

        <DialogFooter className="-mx-6 px-6">
          <fetcher.Form
            method="post"
            action={`./${credentials.id}`}
            className="flex items-center gap-4 w-full"
          >
            <input type="hidden" name="intent" value="delete" />
            <input
              type="hidden"
              name="username"
              value={credentials.username ?? ""}
            />
            <input type="hidden" name="url" value={credentials.url ?? ""} />
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
