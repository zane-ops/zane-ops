import { createFileRoute, useNavigate } from "@tanstack/react-router";
import {
  ArrowDown,
  ArrowUp,
  ChevronsUpDown,
  Folder,
  Rocket,
  Search,
  Settings,
  Trash
} from "lucide-react";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import { useAuthUser } from "~/components/helper/use-auth-user";
import { MetaTitle } from "~/components/meta-title";
import { Input } from "~/components/ui/input";

import {
  Menubar,
  MenubarContent,
  MenubarContentItem,
  MenubarMenu,
  MenubarTrigger
} from "~/components/ui/menubar";

import { Loader } from "~/components/loader";
import { Pagination } from "~/components/pagination";
import { StatusBadge } from "~/components/status-badge";

import { useDebounce } from "use-debounce";
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
import { projectSearchSchema } from "~/key-factories";
import {
  useArchivedProjectList,
  useProjectList
} from "~/lib/hooks/use-project-list";
import { cn } from "~/lib/utils";
import { formattedDate } from "~/utils";

export const Route = createFileRoute("/_dashboard/")({
  validateSearch: (search) => projectSearchSchema.parse(search),
  component: withAuthRedirect(AuthedView)
});

function AuthedView() {
  const query = useAuthUser();
  const user = query.data?.data?.user;

  if (!user) {
    return null;
  }

  return (
    <dl>
      <h1>
        <MetaTitle title="Dashboard" />
        <ProjectList />
      </h1>
    </dl>
  );
}

export function ProjectList() {
  const {
    slug = "",
    page = 1,
    per_page = 10,
    sort_by = ["-updated_at"],
    status = ["active"]
  } = Route.useSearch();
  const [debouncedValue] = useDebounce(slug, 300);

  const navigate = useNavigate();

  const filters = {
    slug: debouncedValue,
    page,
    per_page,
    sort_by
  };

  const projectActiveQuery = useProjectList(filters);
  const projectArchivedQuery = useArchivedProjectList(filters);

  const query = status === "active" ? projectActiveQuery : projectArchivedQuery;

  if (query.isLoading || projectArchivedQuery.isLoading) {
    return <Loader />;
  }

  const projectList = query.data?.data?.results ?? [];
  const totalProjects = query.data?.data?.count ?? 0;
  const totalPages = Math.ceil(totalProjects / per_page);

  const noResults = projectList.length === 0 && debouncedValue.trim() !== "";
  const empty = projectList.length === 0 && debouncedValue.trim() === "";

  const noArchivedProjects = status === "active" && projectList.length === 0;
  const noActiveProjects = status === "archived" && projectList.length === 0;

  const handleSort = (field: "slug" | "updated_at") => {
    const isDescending = sort_by.includes(`-${field}`);
    const newSortBy = sort_by.filter(
      (criteria) => criteria !== field && criteria !== `-${field}`
    );
    newSortBy.push(isDescending ? field : `-${field}`);
    navigate({
      search: { slug, page, per_page, sort_by: newSortBy },
      replace: true
    });
  };

  const getArrowDirection = (field: "slug" | "updated_at") => {
    if (sort_by.includes(`-${field}`)) {
      return "descending";
    }
    return "ascending";
  };
  const slugDirection = getArrowDirection("slug");
  const updatedAtDirection = getArrowDirection("updated_at");

  return (
    <main>
      {empty ? (
        <section className="flex gap-3 flex-col items-center justify-center flex-grow h-[75vh]">
          <div>
            <h1 className="text-2xl font-bold">Welcome to ZaneOps</h1>
            <h1 className="text-lg">You don't have any project yet</h1>
          </div>
          <Button>Create One</Button>
        </section>
      ) : (
        <section>
          <div className="md:my-10 my-5">
            <h1 className="text-3xl font-bold">Overview</h1>
            <h4 className="text-sm mt-2 opacity-60">List of projects</h4>
          </div>

          <div className="flex my-3 flex-wrap items-center md:gap-3 gap-1">
            <div className="flex md:my-5 md:w-[30%] w-full items-center">
              <Search size={20} className="relative left-5" />
              <Input
                onChange={(e) => {
                  navigate({
                    search: {
                      slug: e.target.value,
                      page: 1,
                      per_page,
                      sort_by,
                      status
                    },
                    replace: true
                  });
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
                    <div
                      onClick={() =>
                        navigate({
                          search: {
                            slug,
                            page: 1,
                            per_page,
                            sort_by,
                            status: "Active"
                          },
                          replace: true
                        })
                      }
                    >
                      <MenubarContentItem icon={Rocket} text="Active" />
                    </div>

                    <div
                      onClick={() =>
                        navigate({
                          search: {
                            slug,
                            page: 1,
                            per_page,
                            sort_by,
                            status: "Archived"
                          },
                          replace: true
                        })
                      }
                    >
                      <MenubarContentItem icon={Trash} text="Archived" />
                    </div>
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
                          onClick={() => handleSort("updated_at")}
                          className="flex cursor-pointer items-center gap-2"
                        >
                          Last Updated
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
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {noArchivedProjects ? (
                <TableRow className="border-border cursor-pointer">
                  <TableCell colSpan={5} className="text-center py-4">
                    <h1 className="text-2xl font-bold">No Archived Project</h1>
                  </TableCell>
                </TableRow>
              ) : (
                ""
              )}
              {noResults ? (
                <TableRow className="border-border cursor-pointer">
                  <TableCell colSpan={5} className="text-center py-4">
                    <h1 className="text-2xl font-bold">No results found</h1>
                  </TableCell>
                </TableRow>
              ) : (
                projectList.map((project) => (
                  <TableRow
                    className="border-border cursor-pointer"
                    key={project.id}
                  >
                    <TableCell className="font-medium ">
                      <div className="flex gap-2">
                        <Folder size={18} />
                        {project.slug}
                      </div>
                    </TableCell>
                    <TableCell>{project.description}</TableCell>
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
                          {`${project.total_services} Services Up`}
                        </p>
                      </StatusBadge>
                    </TableCell>
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

          {!noResults && (
            <div
              className={cn("my-4 block", {
                hidden: noArchivedProjects,
                "opacity-40 pointer-events-none": slug !== debouncedValue
              })}
            >
              <Pagination
                totalPages={totalPages}
                currentPage={page}
                perPage={per_page}
                onChangePage={(newPage) => {
                  navigate({
                    search: { slug, page: newPage, per_page, sort_by, status },
                    replace: true
                  });
                }}
                onChangePerPage={(newPerPage) => {
                  navigate({
                    search: {
                      slug,
                      page: 1,
                      per_page: newPerPage,
                      sort_by,
                      status
                    },
                    replace: true
                  });
                }}
              />
            </div>
          )}
        </section>
      )}
    </main>
  );
}
