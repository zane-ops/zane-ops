import { createFileRoute, useNavigate } from "@tanstack/react-router";
import {
  ArrowDown,
  ArrowUp,
  ChevronsUpDown,
  Folder,
  Rocket,
  Search,
  Settings,
  Trash,
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
  MenubarTrigger,
} from "~/components/ui/menubar";

import { Loader } from "~/components/loader";
import { Pagination } from "~/components/pagination";
import { StatusBadge } from "~/components/status-badge";

import { useDebounce } from "use-debounce";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "~/components/ui/table";
import { useProjectList } from "~/lib/hooks/use-project-list";
import { formattedDate } from "~/utils";

import { z } from "zod";
import { Button } from "~/components/ui/button";
import { cn } from "~/lib/utils";

const projectSearchSchema = z.object({
  slug: z.string().catch(""),
  page: z.number().catch(1),
  per_page: z.number().catch(10),
  sort_by: z
    .array(z.enum(["slug", "-slug", "updated_at", "-updated_at"]))
    .optional()
    .catch(["-updated_at"]),
});

type ProjectSearch = z.infer<typeof projectSearchSchema>;

export const Route = createFileRoute("/_dashboard/")({
  validateSearch: (search) => projectSearchSchema.parse(search),
  component: withAuthRedirect(AuthedView),
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
    slug,
    page = 1,
    per_page = 10,
    sort_by = ["-updated_at"],
  } = Route.useSearch();
  const [debouncedValue] = useDebounce(slug, 300);

  const query = useProjectList({
    slug: debouncedValue,
    page,
    per_page,
    sort_by,
  });
  const navigate = useNavigate();

  if (query.isLoading) {
    return <Loader />;
  }

  const projectList = query.data?.data?.results ?? [];
  const totalProjects = query.data?.data?.count ?? 0;
  const totalPages = Math.ceil(totalProjects / per_page);

  const noResults = projectList.length === 0 && debouncedValue.trim() !== "";
  const empty = projectList.length === 0 && debouncedValue.trim() === "";

  const handleSort = (field: "slug" | "updated_at") => {
    const isDescending = sort_by.includes(`-${field}`);
    const newSortBy = sort_by.filter(
      (criteria) => criteria !== field && criteria !== `-${field}`
    );
    newSortBy.push(isDescending ? field : `-${field}`);
    navigate({
      search: { slug, page, per_page, sort_by: newSortBy },
      replace: true,
    });
  };

  const getArrowDirection = (field: "slug" | "updated_at") => {
    if (sort_by.includes(field)) {
      return <ArrowDown size={15} />;
    } else if (sort_by.includes(`-${field}`)) {
      return <ArrowUp size={15} />;
    }
    return <ArrowDown size={15} />;
  };

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
                    },
                    replace: true,
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
                    <MenubarContentItem icon={Rocket} text="Active" />
                    <MenubarContentItem icon={Trash} text="Archived" />
                  </MenubarContent>
                </MenubarMenu>
              </Menubar>
            </div>
          </div>

          <Table>
            <TableHeader className="bg-toggle">
              <TableRow className="border-none">
                <TableHead>
                  <button
                    onClick={() => handleSort("slug")}
                    className="flex cursor-pointer items-center gap-2"
                  >
                    Name
                    {getArrowDirection("slug")}
                  </button>
                </TableHead>
                <TableHead>Description</TableHead>
                <TableHead>
                  <button
                    onClick={() => handleSort("updated_at")}
                    className="flex cursor-pointer items-center gap-2"
                  >
                    Last Updated
                    {getArrowDirection("updated_at")}
                  </button>
                </TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
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
              className={cn(
                "my-4",
                slug !== debouncedValue && "opacity-40 pointer-events-none"
              )}
            >
              <Pagination
                totalPages={totalPages}
                currentPage={page}
                perPage={per_page}
                onChangePage={(newPage) => {
                  navigate({
                    search: { slug, page: newPage, per_page, sort_by },
                    replace: true,
                  });
                }}
                onChangePerPage={(newPerPage) => {
                  navigate({
                    search: { slug, page: 1, per_page: newPerPage, sort_by },
                    replace: true,
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
