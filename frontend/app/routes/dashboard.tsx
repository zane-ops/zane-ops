import type { Route } from "./+types/dashboard";

import {
  ArrowDown01Icon,
  ArrowDownAZIcon,
  ArrowUp10Icon,
  ArrowUpZAIcon,
  ChevronsUpDownIcon,
  FolderIcon,
  LoaderIcon,
  SearchIcon,
  SettingsIcon
} from "lucide-react";

import { Link, useNavigate, useSearchParams } from "react-router";
import { Input } from "~/components/ui/input";

import { Pagination } from "~/components/pagination";
import { StatusBadge } from "~/components/status-badge";

import { useQuery } from "@tanstack/react-query";
import { useSpinDelay } from "spin-delay";
import { useDebouncedCallback } from "use-debounce";
import { Button } from "~/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "~/components/ui/table";

import { SPIN_DELAY_DEFAULT_OPTIONS } from "~/lib/constants";
import {
  projectQueries,
  projectSearchSchema,
  userQueries
} from "~/lib/queries";
import { cn } from "~/lib/utils";
import { queryClient } from "~/root";
import { formattedDate, pluralize } from "~/utils";

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const searchParams = new URL(request.url).searchParams;

  const search = projectSearchSchema.parse(searchParams);
  const {
    slug = "",
    page = 1,
    per_page = 10,
    sort_by = ["-updated_at"]
  } = search;
  const filters = {
    slug,
    page,
    per_page,
    sort_by
  };

  // fetch the data on first load to prevent showing the loading fallback
  const projectList = await queryClient.ensureQueryData(
    projectQueries.list(filters)
  );

  return {
    projectList
  };
}

type SortDirection = "ascending" | "descending" | "indeterminate";

export default function ProjectList({ loaderData }: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const search = projectSearchSchema.parse(searchParams);
  const { slug = "", page = 1, per_page = 10, sort_by } = search;

  const navigate = useNavigate();

  const filters = {
    slug,
    page,
    per_page,
    sort_by
  };

  const projectActiveQuery = useQuery({
    ...projectQueries.list(filters),
    initialData: loaderData.projectList
  });

  const query = projectActiveQuery;

  const projectList = query.data?.results ?? [];
  const totalProjects = query.data?.count ?? 0;
  const totalPages = Math.ceil(totalProjects / per_page);

  const noResults = projectList.length === 0 && slug.trim() !== "";

  const emptySearchParams =
    !(searchParams.get("slug")?.trim() ?? "") &&
    !searchParams.get("sort_by") &&
    !searchParams.get("per_page") &&
    !searchParams.get("page");

  const toggleSort = (field: "slug" | "updated_at") => {
    let nextDirection: SortDirection = "ascending";

    if (sort_by?.includes(field)) {
      nextDirection = "descending";
    } else if (sort_by?.includes(`-${field}`)) {
      nextDirection = "indeterminate";
    }

    let newSortBy = (sort_by ?? []).filter(
      (sort_field) => sort_field !== field && sort_field !== `-${field}`
    );
    switch (nextDirection) {
      case "ascending": {
        newSortBy.push(field);
        break;
      }
      case "descending": {
        newSortBy.push(`-${field}`);
        break;
      }
    }

    searchParams.delete("sort_by");
    newSortBy.forEach((sort_by) => {
      searchParams.append(`sort_by`, sort_by.toString());
    });

    setSearchParams(searchParams, {
      replace: true
    });
  };

  const getArrowDirection = (field: "slug" | "updated_at"): SortDirection => {
    if (sort_by?.includes(`-${field}`)) {
      return "descending";
    } else if (sort_by?.includes(field)) {
      return "ascending";
    }
    return "indeterminate";
  };

  const noProjects = projectList.length === 0;
  const slugDirection = getArrowDirection("slug");
  const updatedAtDirection = getArrowDirection("updated_at");

  const searchProjects = useDebouncedCallback((slug: string) => {
    searchParams.set("slug", slug);
    setSearchParams(searchParams, { replace: true });
  }, 300);

  const isFetchingProjects = useSpinDelay(
    query.isFetching,
    SPIN_DELAY_DEFAULT_OPTIONS
  );

  return (
    <main>
      <section>
        <div className="md:my-10 my-5">
          <h1 className="text-3xl font-bold">Overview</h1>
          <h4 className="text-sm mt-2 opacity-60">List of projects</h4>
        </div>

        <div className="flex my-3 flex-wrap items-center md:gap-3 gap-1">
          <div className="flex md:my-5 md:w-[30%] w-full items-center">
            {isFetchingProjects ? (
              <LoaderIcon size={20} className="animate-spin relative left-4" />
            ) : (
              <SearchIcon size={20} className="relative left-4" />
            )}

            <Input
              onChange={(e) => {
                searchProjects(e.currentTarget.value);
              }}
              defaultValue={slug}
              className="px-14 -mx-5 w-full my-1 text-sm focus-visible:right-0"
              placeholder="Ex: ZaneOps"
            />
          </div>
        </div>

        <Table>
          <TableHeader className="bg-toggle">
            <TableRow className="border-none">
              <TableHead>
                <button
                  onClick={() => toggleSort("slug")}
                  className="flex cursor-pointer items-center gap-2"
                >
                  <span>Name</span>
                  {slugDirection === "indeterminate" && (
                    <ChevronsUpDownIcon size={15} className="flex-none" />
                  )}
                  {slugDirection === "ascending" && (
                    <ArrowDownAZIcon size={15} className="flex-none" />
                  )}
                  {slugDirection === "descending" && (
                    <ArrowUpZAIcon size={15} className="flex-none" />
                  )}
                </button>
              </TableHead>
              <TableHead className="hidden md:table-cell">
                Description
              </TableHead>
              <TableHead>
                <button
                  onClick={() => toggleSort("updated_at")}
                  className="flex cursor-pointer items-center gap-2 w-max"
                >
                  <span>Last Updated</span>

                  {updatedAtDirection === "indeterminate" && (
                    <ChevronsUpDownIcon size={15} className="flex-none" />
                  )}

                  {updatedAtDirection === "ascending" && (
                    <ArrowDown01Icon size={15} className="flex-none" />
                  )}
                  {updatedAtDirection === "descending" && (
                    <ArrowUp10Icon size={15} className="flex-none" />
                  )}
                </button>
              </TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {emptySearchParams && noProjects && (
              <TableRow className="border-border">
                <TableCell colSpan={5} className="text-center py-4">
                  <section className="flex gap-3 flex-col items-center justify-center grow py-20">
                    <div>
                      <h1 className="text-2xl font-bold">Welcome to ZaneOps</h1>
                      <h2 className="text-lg">
                        You don't have any project yet
                      </h2>
                    </div>
                    <Button asChild>
                      <Link prefetch="intent" to="/create-project">
                        Create One
                      </Link>
                    </Button>
                  </section>
                </TableCell>
              </TableRow>
            )}

            {noResults ? (
              <TableRow className="border-border">
                <TableCell colSpan={5} className="text-center py-4">
                  <p className="text-2xl font-bold">No results found</p>
                </TableCell>
              </TableRow>
            ) : (
              projectList.map((project) => (
                <TableRow className="border-border" key={project.id}>
                  <TableCell className="font-medium ">
                    <Link
                      className={cn("flex gap-2", "hover:underline")}
                      prefetch="viewport"
                      to={`/project/${project.slug}`}
                    >
                      <FolderIcon size={18} />
                      {project.slug}
                    </Link>
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    {project.description}
                  </TableCell>
                  <TableCell>{formattedDate(project.updated_at)}</TableCell>

                  <TableCell>
                    <StatusBadge
                      color={
                        project.healthy_services === project.total_services
                          ? "green"
                          : project.healthy_services === 0
                            ? "red"
                            : "yellow"
                      }
                    >
                      <p>
                        {project.healthy_services}/
                        {`${project.total_services} ${pluralize("Service", project.total_services)} healthy`}
                      </p>
                    </StatusBadge>
                  </TableCell>

                  <TableCell className="flex justify-end">
                    <Link
                      to={`/project/${project.slug}/settings`}
                      className="w-fit flex items-center gap-3 hover:underline"
                    >
                      Settings
                      <SettingsIcon width={18} />
                    </Link>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>

        <div
          className={cn("my-4 block", {
            "opacity-40 pointer-events-none": query.isFetching
          })}
        >
          {!noResults && !emptySearchParams && totalProjects > 10 && (
            <Pagination
              totalPages={totalPages}
              currentPage={page}
              perPage={per_page}
              onChangePage={(newPage) => {
                searchParams.set(`page`, newPage.toString());
                navigate(`?${searchParams.toString()}`, {
                  replace: true
                });
              }}
              onChangePerPage={(newPerPage) => {
                searchParams.set(`per_page`, newPerPage.toString());
                searchParams.set(`page`, "1");
                navigate(`?${searchParams.toString()}`, {
                  replace: true
                });
              }}
            />
          )}
        </div>
      </section>
    </main>
  );
}
