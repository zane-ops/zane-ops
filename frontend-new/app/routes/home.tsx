import type { Route } from "./+types/home";

import {
  ArrowDown,
  ArrowUp,
  ChevronsUpDown,
  Folder,
  LoaderIcon,
  Rocket,
  Search,
  Settings,
  Trash
} from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { Input } from "~/components/ui/input";

import {
  Menubar,
  MenubarContent,
  MenubarContentItem,
  MenubarMenu,
  MenubarTrigger
} from "~/components/ui/menubar";

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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { SPIN_DELAY_DEFAULT_OPTIONS } from "~/lib/constants";
import { projectQueries, projectSearchSchema } from "~/lib/queries";
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
    sort_by = ["-updated_at"],
    status = "active"
  } = search;
  const filters = {
    slug,
    page,
    per_page,
    sort_by,
    status
  };

  const data = queryClient.getQueriesData({
    exact: false,
    predicate: (query) =>
      query.queryKey.includes(projectQueries.list(filters).queryKey[0]) ||
      query.queryKey.includes(projectQueries.archived(filters).queryKey[0])
  });

  // fetch the data on first load to prevent showing the loading fallback
  if (data.length === 0) {
    await Promise.all([
      queryClient.ensureQueryData(projectQueries.list(filters)),
      queryClient.ensureQueryData(projectQueries.archived(filters))
    ]);
  } else {
    queryClient.prefetchQuery(projectQueries.list(filters));
    queryClient.prefetchQuery(projectQueries.archived(filters));
  }

  return;
}

export default function ProjectList({}: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const search = projectSearchSchema.parse(searchParams);
  const {
    slug = "",
    page = 1,
    per_page = 10,
    sort_by = ["-updated_at"],
    status = "active"
  } = search;

  const navigate = useNavigate();

  const filters = {
    slug,
    page,
    per_page,
    sort_by,
    status
  };

  const projectActiveQuery = useQuery(projectQueries.list(filters));
  const projectArchivedQuery = useQuery(projectQueries.archived(filters));

  const query = status === "active" ? projectActiveQuery : projectArchivedQuery;

  const projectList = query.data?.data?.results ?? [];
  const totalProjects = query.data?.data?.count ?? 0;
  const totalPages = Math.ceil(totalProjects / per_page);

  const noResults =
    projectList.length === 0 && slug.trim() !== "" && status === "active";

  const emptySearchParams =
    !(searchParams.get("slug")?.trim() ?? "") &&
    !searchParams.get("sort_by") &&
    !searchParams.get("status") &&
    !searchParams.get("per_page") &&
    !searchParams.get("page");

  const noActiveProjects = status === "active" && projectList.length === 0;
  const noArchivedProject = status === "archived" && projectList.length === 0;

  const handleSort = (field: "slug" | "updated_at" | "archived_at") => {
    const isDescending = sort_by.includes(`-${field}`);
    const newSortBy = sort_by.filter(
      (criteria) => criteria !== field && criteria !== `-${field}`
    );
    newSortBy.push(isDescending ? field : `-${field}`);
    searchParams.delete("sort_by");
    newSortBy.forEach((sort_by) => {
      searchParams.append(`sort_by`, sort_by.toString());
    });

    setSearchParams(searchParams, {
      replace: true
    });
  };

  const getArrowDirection = (field: "slug" | "updated_at" | "archived_at") => {
    if (sort_by.includes(`-${field}`)) {
      return "descending";
    }
    return "ascending";
  };
  const slugDirection = getArrowDirection("slug");
  const updatedAtDirection =
    status === "active"
      ? getArrowDirection("updated_at")
      : getArrowDirection("archived_at");

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
              <Search size={20} className="relative left-4" />
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

          <div className="md:w-fit w-full">
            <Menubar className="border border-border md:w-fit w-full">
              <MenubarMenu>
                <MenubarTrigger className="flex md:w-fit w-full ring-secondary md:justify-center justify-between text-sm items-center gap-1">
                  Status
                  <ChevronsUpDown className="w-4" />
                </MenubarTrigger>
                <MenubarContent className="border w-[calc(var(--radix-menubar-trigger-width)+0.5rem)] border-border md:min-w-6 md:w-auto">
                  <MenubarContentItem
                    onClick={() => {
                      searchParams.set("page", "1");
                      searchParams.set("status", "active");
                      setSearchParams(searchParams, { replace: true });
                    }}
                    icon={Rocket}
                    text="Active"
                  />

                  <MenubarContentItem
                    onClick={() => {
                      searchParams.set("page", "1");
                      searchParams.set("status", "archived");
                      setSearchParams(searchParams, { replace: true });
                    }}
                    icon={Trash}
                    text="Archived"
                  />
                </MenubarContent>
              </MenubarMenu>
            </Menubar>
          </div>
        </div>

        <Table>
          <TableHeader className="bg-toggle">
            <TableRow className="border-none">
              <TableHead>
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger asChild>
                      <button
                        onClick={() => handleSort("slug")}
                        className="flex cursor-pointer items-center gap-2"
                      >
                        Name
                        {slugDirection === "ascending" ? (
                          <ArrowDown size={15} />
                        ) : (
                          <ArrowUp size={15} />
                        )}
                      </button>
                    </TooltipTrigger>
                    <TooltipContent>
                      <div className="capitalize">{slugDirection}</div>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </TableHead>
              <TableHead>Description</TableHead>
              <TableHead>
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger asChild>
                      <button
                        onClick={() =>
                          status === "active"
                            ? handleSort("updated_at")
                            : handleSort("archived_at")
                        }
                        className="flex cursor-pointer items-center gap-2"
                      >
                        {status === "active" ? "Last Updated" : "Archived At"}
                        {updatedAtDirection === "ascending" ? (
                          <ArrowDown size={15} />
                        ) : (
                          <ArrowUp size={15} />
                        )}
                      </button>
                    </TooltipTrigger>
                    <TooltipContent>
                      <div className="capitalize">{updatedAtDirection}</div>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </TableHead>
              <TableHead
                className={cn({
                  hidden: status === "archived"
                })}
              >
                Status
              </TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {emptySearchParams && noActiveProjects ? (
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
            ) : (
              ""
            )}

            {noArchivedProject && (
              <TableRow className="border-border">
                <TableCell colSpan={5} className="text-center py-4">
                  <p className="text-2xl font-bold">No archived project</p>
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
                      className={cn(
                        "flex gap-2",
                        status === "active" && "hover:underline"
                      )}
                      prefetch="viewport"
                      to={
                        status !== "active" ? "#" : `/project/${project.slug}`
                      }
                    >
                      <Folder size={18} />
                      {project.slug}
                    </Link>
                  </TableCell>
                  <TableCell>{project.description}</TableCell>
                  {"updated_at" in project ? (
                    <TableCell>{formattedDate(project.updated_at)}</TableCell>
                  ) : (
                    <TableCell>{formattedDate(project.archived_at)}</TableCell>
                  )}

                  {"healthy_services" in project && (
                    <TableCell
                      className={cn({
                        hidden: status === "archived"
                      })}
                    >
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
                  )}

                  <TableCell className="flex justify-end">
                    <div className="w-fit flex items-center gap-3">
                      Settings
                      <Settings width={18} />
                    </div>
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
