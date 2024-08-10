import { Popover } from "@radix-ui/react-popover";
import { createFileRoute, Link } from "@tanstack/react-router";
import {
  CalendarIcon,
  ChevronsUpDown,
  Container,
  KeyRound,
  Rocket,
  Settings,
  Trash,
  TriangleAlert
} from "lucide-react";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import { MetaTitle } from "~/components/meta-title";
import { StatusBadge } from "~/components/status-badge";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from "~/components/ui/breadcrumb";
import { Button } from "~/components/ui/button";
import { Calendar } from "~/components/ui/calendar";
import { PopoverContent, PopoverTrigger } from "~/components/ui/popover";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "~/components/ui/tabs";
import * as React from "react";
import type { DateRange } from "react-day-picker";
import { addDays, format } from "date-fns";
import { cn } from "~/lib/utils";
import {
  Menubar,
  MenubarContent,
  MenubarContentItem,
  MenubarMenu,
  MenubarTrigger
} from "~/components/ui/menubar";
export const Route = createFileRoute(
  "/_dashboard/project/$project_slug/services/docker/$service_slug"
)({
  component: withAuthRedirect(ServiceDetails)
});

function ServiceDetails() {
  const { project_slug, service_slug } = Route.useParams();
  const baseUrl = `/project/${project_slug}/services/docker/${service_slug}`;
  const [date, setDate] = React.useState<DateRange | undefined>({
    from: new Date(2022, 0, 20),
    to: addDays(new Date(2022, 0, 20), 20)
  });
  return (
    <>
      <MetaTitle title={`${service_slug}`} />
      <Breadcrumb>
        <BreadcrumbList className="text-sm">
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/">Projects</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to={`/project/${project_slug}/`}>{project_slug}</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>

          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{service_slug}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <div className="flex items-center justify-between">
        <div className="mt-10">
          <h1 className="text-2xl">nginxdemo</h1>
          <p className="flex gap-1 items-center">
            <Container size={15} />{" "}
            <span className="text-gray-400 text-sm">
              nginxdemo/hello:latest
            </span>
          </p>
          <div className="flex gap-3 items-center">
            <Link className="underline text-link text-sm">
              nginxdemo.zaneops.local
            </Link>
            <StatusBadge
              className="relative top-0.5 text-xs"
              color="gray"
              isPing={false}
            >
              +2 urls
            </StatusBadge>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="warning">
            <TriangleAlert size={15} />
            <span className="mx-1">1 unapplied change</span>
          </Button>

          <Button variant="secondary">deploy</Button>
        </div>
      </div>
      <Tabs defaultValue="deployment" className="w-full mt-5">
        <TabsList className="w-full items-start justify-start bg-background rounded-none border-b border-border">
          <TabsTrigger value="deployment" asChild>
            <Link className="flex gap-2 items-center" to={baseUrl}>
              Deployments <Rocket size={15} />
            </Link>
          </TabsTrigger>

          <TabsTrigger value="envVariable">
            <Link
              className="flex gap-2 items-center"
              to={`${baseUrl}/env-variables`}
            >
              Env Variables <KeyRound size={15} />
            </Link>
          </TabsTrigger>

          <TabsTrigger value="settings">
            <Link
              className="flex gap-2 items-center"
              to={`${baseUrl}/settings`}
            >
              Settings <Settings size={15} />
            </Link>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="deployment">
          <div className="flex mt-8 gap-2">
            <Popover>
              <PopoverTrigger asChild>
                <Button
                  id="date"
                  variant={"outline"}
                  className={cn(
                    "w-[300px] justify-start text-left font-normal",
                    !date && "text-muted-foreground"
                  )}
                >
                  <CalendarIcon className="mr-2 h-4 w-4" />
                  {date?.from ? (
                    date.to ? (
                      <>
                        {format(date.from, "LLL dd, y")} -{" "}
                        {format(date.to, "LLL dd, y")}
                      </>
                    ) : (
                      format(date.from, "LLL dd, y")
                    )
                  ) : (
                    <span>Pick a date</span>
                  )}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="start">
                <Calendar
                  initialFocus
                  mode="range"
                  defaultMonth={date?.from}
                  selected={date}
                  onSelect={setDate}
                  numberOfMonths={2}
                />
              </PopoverContent>
            </Popover>
            <Menubar className="border border-border md:w-fit w-full">
              <MenubarMenu>
                <MenubarTrigger className="flex md:w-fit w-full ring-secondary md:justify-center justify-between text-sm items-center gap-1">
                  Status
                  <ChevronsUpDown className="w-4" />
                </MenubarTrigger>
                <MenubarContent className="border w-[calc(var(--radix-menubar-trigger-width)+0.5rem)] border-border md:min-w-6 md:w-auto">
                  <Status color="gray">
                    <MenubarContentItem text="Queued" />
                  </Status>
                  <Status color="gray">
                    <MenubarContentItem text="Canceled" />
                  </Status>
                  <Status color="red">
                    <MenubarContentItem text="Failed" />
                  </Status>

                  <Status color="gray">
                    <MenubarContentItem text="Preparing" />
                  </Status>

                  <Status color="blue">
                    <MenubarContentItem text="Starting" />
                  </Status>

                  <Status color="blue">
                    <MenubarContentItem text="Restarting" />
                  </Status>

                  <Status color="green">
                    <MenubarContentItem text="Healthy" />
                  </Status>

                  <Status color="red">
                    <MenubarContentItem text="Unhealthy" />
                  </Status>

                  <Status color="gray">
                    <MenubarContentItem text="Removed" />
                  </Status>

                  <Status color="orange">
                    <MenubarContentItem text="Sleeping" />
                  </Status>
                </MenubarContent>
              </MenubarMenu>
            </Menubar>
          </div>

          {/**
     * <div className="flex justify-center items-center">
            <div className=" flex gap-1 flex-col items-center mt-40">
              <h1 className="text-2xl font-bold">No Deployments made yet</h1>
              <h2 className="text-lg">Your service is offline</h2>
              <Button>
                <Link to={`create-service`}> Deploy now</Link>
              </Button>
            </div>
          </div>
     */}
        </TabsContent>

        <TabsContent value="envVariable"></TabsContent>
        <TabsContent value="settings"></TabsContent>
      </Tabs>
    </>
  );
}

type TrackerColor = "red" | "green" | "orange" | "gray" | "blue";

interface StatusProps {
  color: TrackerColor;
  children: React.ReactNode;
  isPing?: boolean;
  className?: string;
}

function Status({ children, color, className }: StatusProps) {
  return (
    <div className="flex items-center">
      <div
        className={cn(
          "relative rounded-full bg-green-400 w-2 h-2",
          {
            "bg-green-600 ": color === "green",
            "bg-red-400": color === "red",
            "bg-orange-400": color === "orange",
            "bg-gray-400": color === "gray"
          },
          className
        )}
      ></div>
      {children}
    </div>
  );
}
