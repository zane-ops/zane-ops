import { createLazyFileRoute } from "@tanstack/react-router";
import {
  ArrowDown,
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

import React from "react";
import { Loader } from "~/components/loader";
import { Pagination } from "~/components/pagination";
import { StatusBadge } from "~/components/status-badge";
import { Button } from "~/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "~/components/ui/table";
import { useProjectList } from "~/lib/hooks/use-project-list";
import { formattedDate } from "~/utils";

export const Route = createLazyFileRoute("/_dashboard/")({
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
  const [currentPage, setCurrentPage] = React.useState(1);
  const [perPage, setPerPage] = React.useState(10);

  const query = useProjectList();

  if (query.isLoading) {
    return <Loader />;
  }
  const projectList = query.data?.data?.results ?? [];

  return (
    <>
      {projectList.length === 0 ? (
        <main className="flex gap-3 flex-col items-center justify-center flex-grow h-[75vh]">
          <div>
            <h1 className="text-2xl font-bold">Welcome to ZaneOps</h1>
            <h1 className="text-lg">You don't have any project yet</h1>
          </div>
          <Button>Create One</Button>
        </main>
      ) : (
        <main>
          <div className="md:my-10 my-5">
            <h1 className="text-3xl  font-bold">Overview</h1>
            <h4 className="text-sm mt-2 opacity-60">List of projects</h4>
          </div>

          <div className="flex my-3 flex-wrap items-center md:gap-3 gap-1">
            <div className="flex md:my-5 md:w-[30%] w-full  items-center">
              <Search size={20} className="relative left-5" />
              <Input
                className="px-14 -mx-5 w-full my-1 text-sm focus-visible:right-0"
                placeholder="Ex: ZaneOps"
              />
            </div>

            <div className="md:w-fit w-full">
              <Menubar className="border border-border md:w-fit w-full ">
                <MenubarMenu>
                  <MenubarTrigger className="flex md:w-fit w-full ring-secondary md:justify-center justify-between text-sm items-center gap-1">
                    Status
                    <ChevronsUpDown className="w-4" />
                  </MenubarTrigger>
                  <MenubarContent className=" border  w-[calc(var(--radix-menubar-trigger-width)+0.5rem)]  border-border md:min-w-6  md:w-auto">
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
                <TableHead>Name</TableHead>
                <TableHead>Description</TableHead>
                <TableHead className="flex items-center gap-2">
                  Last Updated
                  <ArrowDown size={15} />
                </TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {projectList.map((project) => (
                <TableRow
                  className="border-border cursor-pointer"
                  key={project.id}
                >
                  <TableCell className="font-medium flex items-center gap-3">
                    <Folder size={18} />
                    {project.slug}
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
              ))}
            </TableBody>
          </Table>

          <div className="my-4">
            <Pagination
              totalPages={10}
              currentPage={currentPage}
              perPage={perPage}
              onChangePage={(page) => setCurrentPage(page)}
              onChangePerPage={(perPage) => setPerPage(perPage)}
            />
          </div>
        </main>
      )}
    </>
  );
}
