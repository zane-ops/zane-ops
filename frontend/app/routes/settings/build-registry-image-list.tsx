import { useQuery } from "@tanstack/react-query";
import {
  ChevronRightIcon,
  ChevronsLeftIcon,
  ExternalLinkIcon,
  TagsIcon
} from "lucide-react";
import { Link, useSearchParams } from "react-router";
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
  buildRegistryImageListFilters,
  buildRegistryQueries
} from "~/lib/queries";
import { queryClient } from "~/root";
import { metaTitle } from "~/utils";
import type { Route } from "./+types/build-registry-image-list";

export function meta() {
  return [
    metaTitle("Registry Image List")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({
  params,
  request
}: Route.ClientLoaderArgs) {
  const searchParams = new URL(request.url).searchParams;
  const search = buildRegistryImageListFilters.parse(searchParams);

  const [registry, imageList] = await Promise.all([
    queryClient.ensureQueryData(buildRegistryQueries.single(params.id)),
    queryClient.ensureQueryData(
      buildRegistryQueries.imageList(params.id, {
        cursor: search.cursor
      })
    )
  ]);
  return {
    registry,
    imageList
  };
}

export default function BuildRegistryImageListPage({
  loaderData,
  params
}: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const search = buildRegistryImageListFilters.parse(searchParams);

  const { data: imageList } = useQuery({
    ...buildRegistryQueries.imageList(params.id, {
      cursor: search.cursor
    }),
    initialData: loaderData.imageList
  });

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">
          Images included in&nbsp;
          <span>`</span>
          {loaderData.registry.name}
          <span>`</span>
        </h2>
      </div>
      <Separator />
      <h3 className="text-grey">
        List of docker images pushed to{" "}
        <a
          href={`${loaderData.registry.is_secure ? "https" : "http"}://${loaderData.registry.registry_domain}`}
          target="_blank"
          className="underline text-link inline-flex items-center gap-1"
        >
          <span>{`${loaderData.registry.is_secure ? "https" : "http"}://${loaderData.registry.registry_domain}`}</span>
          <ExternalLinkIcon size={16} className="flex-none" />
        </a>
      </h3>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="sticky top-0 z-20">Name</TableHead>
          </TableRow>
        </TableHeader>

        <TableBody className="w-full">
          {imageList.results.length === 0 && (
            <TableRow className="px-2">
              <TableCell className="p-2 text-muted-foreground italic">
                -- No Images pushed yet --
              </TableCell>
            </TableRow>
          )}
          {imageList.results.map((image) => (
            <TableRow key={image} className="px-2 w-full">
              <TableCell className="p-2">
                <div className="flex gap-2 items-center">
                  <TagsIcon className="flex-none size-4 text-grey relative top-0.5" />
                  <span className="inline-flex gap-1 items-center">
                    {image}
                  </span>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <div className="flex items-center gap-4 justify-end">
        {search.cursor && (
          <Link
            to="./"
            className="inline-flex gap-2 items-center hover:underline"
          >
            <ChevronsLeftIcon className="size-4 flex-none" />
            Initial page
          </Link>
        )}
        {search.cursor && imageList.cursor && (
          <Separator className="inline-block h-2.5 w-px bg-grey relative top-0.5 rounded-md" />
        )}
        {imageList.cursor && (
          <Link
            to={{
              search: `?cursor=${encodeURIComponent(imageList.cursor)}`
            }}
            className="inline-flex gap-2 items-center hover:underline"
          >
            Next page <ChevronRightIcon className="size-4 flex-none" />
          </Link>
        )}
      </div>
    </section>
  );
}
