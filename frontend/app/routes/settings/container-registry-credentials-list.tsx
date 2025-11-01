import { useQuery } from "@tanstack/react-query";
import {
  ChevronRightIcon,
  ContainerIcon,
  ExternalLinkIcon,
  PlusIcon
} from "lucide-react";
import { Link } from "react-router";
import { AWSECSLogo } from "~/components/aws-ecs-logo";
import { DockerHubLogo } from "~/components/docker-hub-logo";
import { GithubLogo } from "~/components/github-logo";
import { GitlabLogo } from "~/components/gitlab-logo";
import { GoogleArtifactLogo } from "~/components/google-artifact-logo";
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
import { REGISTRY_NAME_MAP } from "~/lib/constants";
import { containerRegistriesQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { capitalizeText, metaTitle } from "~/utils";
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
            <TableHead className="sticky top-0 z-20">Actions</TableHead>
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
            registries.map((registry) => (
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
                    {registry.registry_type === "GENERIC" && (
                      <ContainerIcon className="size-4" />
                    )}
                    {registry.registry_type === "DOCKER_HUB" && (
                      <DockerHubLogo className="size-4 flex-none" />
                    )}
                    {registry.registry_type === "GITHUB" && (
                      <GithubLogo className="size-4 flex-none" />
                    )}
                    {registry.registry_type === "GITLAB" && (
                      <GitlabLogo className="size-6 -m-2 [&_path]:!fill-orange-400 flex-none" />
                    )}
                    {registry.registry_type === "AWS_ECR" && (
                      <AWSECSLogo className="size-4 flex-none" />
                    )}
                    {registry.registry_type === "GOOGLE_ARTIFACT" && (
                      <GoogleArtifactLogo className="size-4 flex-none" />
                    )}

                    {REGISTRY_NAME_MAP[registry.registry_type]}
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
                <TableCell className="p-2">
                  <Link
                    to={`./${registry.id}`}
                    className="inline-flex gap-1 items-center hover:underline"
                  >
                    <span>View details</span>
                    <ChevronRightIcon size={16} className="flex-none" />
                  </Link>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </section>
  );
}
