import { createLazyFileRoute } from "@tanstack/react-router";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import { useAuthUser } from "~/components/helper/use-auth-user";
import { MetaTitle } from "~/components/meta-title";
import {
  AlarmCheck,
  AlertTriangle,
  ArrowDown,
  Check,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  ChevronsUpDown,
  CircleDashed,
  Folder,
  FolderArchive,
  Globe,
  Hammer,
  Rocket,
  Search,
  Settings,
  Trash,
  X,
} from "lucide-react";
import { Input } from "~/components/ui/input";
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "~/components/ui/pagination";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "~/components/ui/table";
import {
  Menubar,
  MenubarContent,
  MenubarMenu,
  MenubarTrigger,
} from "~/components/ui/menubar";
import { MenubarContentItem } from "../_dashboard";
import { NavLink } from "~/components/nav-link";
import { Button } from "~/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "~/components/ui/select";

export const Route = createLazyFileRoute("/_dashboard/")({
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
        <TableDemo />
      </h1>
    </dl>
  );
}

const projects = [
  {
    name: "ZaneOps",
    updated_at: "Jan 13, 2024",
    status: "0/5 Services Up",
    actions: "Settings",
    statusIcon: <X size={14} />,
    tracker: 0,
  },
  {
    name: "ZaneOps",
    updated_at: "Jan 13, 2024",
    status: "5/5 Services Up",
    actions: "Settings",
    statusIcon: <Check size={14} />,
    tracker: 1,
  },
  {
    name: "ZaneOps",
    updated_at: "Jan 13, 2024",
    status: "2/5 Services Up",
    actions: "Settings",
    statusIcon: <AlertTriangle size={14} />,
    tracker: 2,
  },
];

export function TableDemo() {
  return (
    <main>
      <div className="my-10">
        <h1 className="text-3xl  font-bold">Overview</h1>
        <h4 className="text-sm mt-2 opacity-60">List of projects</h4>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex my-5 w-[30%]  items-center">
          <Search size={20} className="relative left-5" />
          <Input
            className="px-14 placeholder:text-gray-400  -mx-5 w-full my-1 text-sm focus-visible:right-0"
            placeholder="Ex: ZaneOps"
          />
        </div>
        <div>
          <Menubar className="border border-border w-fit ">
            <MenubarMenu>
              <MenubarTrigger className="flex ring-secondary justify-center text-sm items-center gap-1">
                Status
                <ChevronsUpDown className="w-4" />
              </MenubarTrigger>
              <MenubarContent className=" border border-border min-w-6">
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
            <TableRow
              className="border-border cursor-pointer"
              key={project.name}
            >
              <TableCell className="font-medium flex items-center gap-3">
                <Folder size={18} />
                {project.name}
              </TableCell>
              <TableCell>{project.updated_at}</TableCell>
              <TableCell>
                <div
                  className={`flex border w-fit px-3 py-1 border-opacity-60 rounded-full text-sm items-center gap-2 ${
                    project.tracker === 1
                      ? "border-green-600 bg-green-600 bg-opacity-10 text-statusgreen"
                      : project.tracker === 0
                        ? "border-red-600 bg-red-600 bg-opacity-10 text-statusred"
                        : project.tracker === 2
                          ? "border-yellow-600 bg-yellow-600 bg-opacity-10 text-statusyellow"
                          : ""
                  }`}
                >
                  <div
                    className={`border w-2 h-2 text-white border-transparent p-0.5 rounded-full ${
                      project.tracker === 1
                        ? "bg-green-600"
                        : project.tracker === 0
                          ? "bg-red-600"
                          : project.tracker === 2
                            ? "bg-yellow-600"
                            : ""
                    }`}
                  ></div>
                  {project.status}
                </div>
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
        <DatatablePagination />
      </div>
    </main>
  );
}

function DatatablePagination() {
  return (
    <div className="flex  items-center justify-end px-2">
      <div className="flex items-center space-x-2">
        <p className="text-sm font-medium">Rows per page</p>
        <Select value="10">
          <SelectTrigger className="h-8 w-[70px]">
            <SelectValue placeholder="10" />
          </SelectTrigger>
          <SelectContent className="border border-border" side="top">
            {[10, 20, 30, 40, 50].map((pageSize) => (
              <SelectItem key={pageSize} value={`${pageSize}`}>
                {pageSize}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex  items-center space-x-6 lg:space-x-8">
        <div className="flex w-[100px] items-center justify-center text-sm font-medium">
          Page of 10
        </div>
        <div className="flex items-center space-x-2">
          <Button variant="outline" className="hidden h-8 w-8 p-0 lg:flex">
            <span className="sr-only">Go to first page</span>
            <ChevronsLeft className="h-4 w-4" />
          </Button>
          <Button variant="outline" className="h-8 w-8 p-0">
            <span className="sr-only">Go to previous page</span>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button variant="outline" className="h-8 w-8 p-0">
            <span className="sr-only">Go to next page</span>
            <ChevronRight className="h-4 w-4" />
          </Button>
          <Button variant="outline" className="hidden h-8 w-8 p-0 lg:flex">
            <span className="sr-only">Go to last page</span>
            <ChevronsRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
