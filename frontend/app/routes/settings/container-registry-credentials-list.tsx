import { useQuery } from "@tanstack/react-query";
import {
  ExternalLinkIcon,
  PencilLineIcon,
  PlusIcon,
  Trash2Icon,
  ZapIcon
} from "lucide-react";
import { Link, useNavigate } from "react-router";
import { StatusBadge } from "~/components/status-badge";
import { Button } from "~/components/ui/button";

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
import { containerRegistriesQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { metaTitle } from "~/utils";
import type { Route } from "./+types/container-registry-credentials-list";

export function meta() {
  return [
    metaTitle("Registry Credentials")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader() {
  const registries = await queryClient.ensureQueryData(
    containerRegistriesQueries.list
  );
  return { registries };
}

export default function ContainerRegistryCredentialsPage({
  loaderData
}: Route.ComponentProps) {
  const { data: registries } = useQuery({
    ...containerRegistriesQueries.list,
    initialData: loaderData.registries
  });

  const navigate = useNavigate();

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Container Registry Credentials</h2>
        <Button asChild variant="secondary" className="flex gap-2">
          <Link to="new" prefetch="intent">
            New <PlusIcon size={18} />
          </Link>
        </Button>
      </div>
      <Separator />
      <h3>Store registry credentials to pull and deploy private images.</h3>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="sticky top-0 z-20">Type</TableHead>
            <TableHead className="sticky top-0 z-20">Username</TableHead>
            <TableHead className="sticky top-0 z-20">URL</TableHead>
            <TableHead className="sticky top-0 z-20 px-4">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {registries.length === 0 ? (
            <TableRow className="px-2">
              <TableCell className="p-2" colSpan={4}>
                No Credentials found
              </TableCell>
            </TableRow>
          ) : (
            registries.map((registry) => {
              const Icon = DEFAULT_REGISTRIES[registry.registry_type].Icon;
              return (
                <TableRow className="px-2" key={registry.id}>
                  <TableCell className="!px-2 py-2">
                    <StatusBadge
                      color={
                        registry.registry_type === "DOCKER_HUB" ||
                        registry.registry_type === "GOOGLE_ARTIFACT"
                          ? "blue"
                          : registry.registry_type === "AWS_ECR" ||
                              registry.registry_type === "GITLAB"
                            ? "yellow"
                            : "gray"
                      }
                      pingState="hidden"
                      className="capitalize"
                    >
                      <Icon />
                      {DEFAULT_REGISTRIES[registry.registry_type].name}
                    </StatusBadge>
                  </TableCell>
                  <TableCell className="p-2">
                    {registry.username ?? (
                      <span className="text-grey font-mono">N/A</span>
                    )}
                  </TableCell>
                  <TableCell className="p-2">
                    <a
                      href={registry.url}
                      target="_blank"
                      className="underline text-link inline-flex items-center gap-1"
                      rel="noreferrer"
                    >
                      <span>{registry.url}</span>
                      <ExternalLinkIcon size={16} className="flex-none" />
                    </a>
                  </TableCell>
                  <TableCell className="p-2 ">
                    <div className="flex items-center gap-1">
                      <TooltipProvider>
                        <Tooltip delayDuration={0}>
                          <TooltipTrigger asChild>
                            <Button
                              size="sm"
                              variant="ghost"
                              asChild
                              className="gap-1"
                            >
                              <Link to={`./${registry.id}`}>
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
                            <Button size="sm" variant="ghost" className="gap-1">
                              <span className="sr-only">Test Connection</span>
                              <ZapIcon className="flex-none size-4" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Test Connection</TooltipContent>
                        </Tooltip>
                        <div className="h-2 relative top-0.5 w-px bg-grey rounded-md" />

                        <Tooltip delayDuration={0}>
                          <TooltipTrigger asChild>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="gap-1 text-red-400"
                            >
                              <>
                                <span className="sr-only">Delete</span>
                                <Trash2Icon className="flex-none size-4" />
                              </>
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>Delete Credentials</TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </div>
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
