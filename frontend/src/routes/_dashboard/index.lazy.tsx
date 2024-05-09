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
  MenubarMenu,
  MenubarTrigger
} from "~/components/ui/menubar";

import React from "react";
import { Pagination } from "~/components/pagination";
import { StatusBadge } from "~/components/status-badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "~/components/ui/table";
import { MenubarContentItem } from "../_dashboard";

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

const projects = [
  {
    id: 1,
    name: "ZaneOps",
    updated_at: "Jan 13, 2024",
    status: "0/5 Services Up",
    actions: "Settings",
    tracker: 0
  },
  {
    id: 2,
    name: "ZaneOps",
    updated_at: "Jan 13, 2024",
    status: "5/5 Services Up",
    actions: "Settings",
    tracker: 1
  },
  {
    id: 3,
    name: "ZaneOps",
    updated_at: "Jan 13, 2024",
    status: "2/5 Services Up",
    actions: "Settings",
    tracker: 2
  }
];

// TODO: to remove
type TrackerColor = "red" | "green" | "yellow";
function getBadgeColor(tracker: number): TrackerColor {
  switch (tracker) {
    case 0:
      return "red";
    case 1:
      return "green";
    case 2:
      return "yellow";
    default:
      return "green";
  }
}

export function ProjectList() {
  const [currentPage, setCurrentPage] = React.useState(1);
  const [perPage, setPerPage] = React.useState(10);

  return (
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
            <TableHead className="flex items-center gap-2">
              Last Updated
              <ArrowDown size={15} />
            </TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {projects.map((project) => (
            <TableRow className="border-border cursor-pointer" key={project.id}>
              <TableCell className="font-medium flex items-center gap-3">
                <Folder size={18} />
                {project.name}
              </TableCell>
              <TableCell>{project.updated_at}</TableCell>
              <TableCell>
                <StatusBadge color={getBadgeColor(project.tracker)}>
                  {project.status}
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
  );
}
