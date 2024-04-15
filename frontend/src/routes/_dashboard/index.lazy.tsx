import { createLazyFileRoute } from "@tanstack/react-router";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import { useAuthUser } from "~/components/helper/use-auth-user";
import { MetaTitle } from "~/components/meta-title";

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
        <TableDemo />
      </h1>
    </dl>
  );
}

import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow
} from "~/components/ui/table";

const projects = [
  {
    name: "ZaneOps",
    updated_at: "Jan 13, 2024",
    status: "0/5 Services Up",
    actions: "Settings",
    statusIcon: <X size={14} />,
    tracker: 0
  },
  {
    name: "ZaneOps",
    updated_at: "Jan 13, 2024",
    status: "5/5 Services Up",
    actions: "Settings",
    statusIcon: <Check size={14} />,
    tracker: 1
  },
  {
    name: "ZaneOps",
    updated_at: "Jan 13, 2024",
    status: "2/5 Services Up",
    actions: "Settings",
    statusIcon: <AlertTriangle size={14} />,
    tracker: 2
  }
];

export function TableDemo() {
  return (
    <main>
      <h1 className="text-3xl my-10 font-bold">Overview</h1>
      <div className="flex my-5 w-[40%]  items-center">
        <Search size={20} className="relative left-5" />
        <Input
          className="px-14 -mx-5 w-full my-1 text-sm focus-visible:right-0"
          placeholder="Ex: ZaneOps"
        />
      </div>

      <Table>
        <TableHeader>
          <TableRow className="border-border">
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
                      ? "border-green-600 bg-green-600 bg-opacity-10 text-green-200"
                      : project.tracker === 0
                        ? "border-red-600 bg-red-600 bg-opacity-10 text-red-200"
                        : project.tracker === 2
                          ? "border-yellow-600 bg-yellow-600 bg-opacity-10 text-yellow-200"
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
        <PaginationDemo />
      </div>
    </main>
  );
}

import {
  AlertTriangle,
  ArrowBigDown,
  ArrowDown,
  ArrowDownNarrowWide,
  Check,
  CheckCircle,
  Cog,
  Folder,
  LucideArrowDownWideNarrow,
  MinusCircle,
  Search,
  Settings,
  X
} from "lucide-react";
import { Input } from "~/components/ui/input";
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious
} from "~/components/ui/pagination";

export function PaginationDemo() {
  return (
    <Pagination>
      <PaginationContent className="w-full flex justify-between">
        <PaginationItem className="border-border border rounded-md">
          <PaginationPrevious href="#" />
        </PaginationItem>
        <div className="flex gap-5">
          <PaginationItem>
            <PaginationLink href="#">1</PaginationLink>
          </PaginationItem>
          <PaginationItem>
            <PaginationLink href="#" isActive>
              2
            </PaginationLink>
          </PaginationItem>
          <PaginationItem>
            <PaginationLink href="#">3</PaginationLink>
          </PaginationItem>
          <PaginationItem>
            <PaginationEllipsis />
          </PaginationItem>
        </div>
        <PaginationItem className="border border-border rounded-md">
          <PaginationNext href="#" />
        </PaginationItem>
      </PaginationContent>
    </Pagination>
  );
}
