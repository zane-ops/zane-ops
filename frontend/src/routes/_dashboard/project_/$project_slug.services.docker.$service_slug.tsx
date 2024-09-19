import { Popover } from "@radix-ui/react-popover";
import { Link, createFileRoute } from "@tanstack/react-router";
import { addDays, format } from "date-fns";
import {
  Ban,
  CalendarIcon,
  Container,
  EllipsisVertical,
  Eye,
  KeyRound,
  Loader,
  Redo2,
  Rocket,
  ScrollText,
  Settings,
  Timer,
  TriangleAlert
} from "lucide-react";
import * as React from "react";
import type { DateRange } from "react-day-picker";
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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";

import {
  Menubar,
  MenubarContent,
  MenubarContentItem,
  MenubarMenu,
  MenubarTrigger
} from "~/components/ui/menubar";
import { MultiSelect } from "~/components/ui/mutiple-select";
import { PopoverContent, PopoverTrigger } from "~/components/ui/popover";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "~/components/ui/tabs";
import { cn } from "~/lib/utils";
import {
  capitalizeText,
  formatElapsedTime,
  mergeTimeAgoFormatterAndFormattedDate
} from "~/utils";

const statuses = [
  { value: "QUEUED", label: "QUEUED", color: "gray" },
  { value: "CANCELLED", label: "CANCELLED", color: "gray" },
  { value: "FAILED", label: "FAILED", color: "red" },
  { value: "PREPARING", label: "PREPARING", color: "blue" },
  { value: "HEALTHY", label: "HEALTHY", color: "green" },
  { value: "UNHEALTHY", label: "UNHEALTHY", color: "red" },
  { value: "STARTING", label: "STARTING", color: "blue" },
  { value: "RESTARTING", label: "RESTARTING", color: "blue" },
  { value: "REMOVED", label: "REMOVED", color: "gray" },
  { value: "SLEEPING", label: "SLEEPING", color: "orange" }
];

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

  const [selectedStatuses, setSelectedStatuses] = React.useState(
    statuses.map((status) => status.value)
  );

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
            <span className="text-gray-500 dark:text-gray-400 text-sm">
              nginxdemo/hello:latest
            </span>
          </p>
          <div className="flex gap-3 items-center">
            <a
              href="https://nginxdemo.zaneops.local"
              target="_blank"
              className="underline text-link text-sm"
            >
              nginxdemo.zaneops.local
            </a>
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <span>
                    <StatusBadge
                      className="relative top-0.5 text-xs cursor-pointer"
                      color="gray"
                      isPing={false}
                    >
                      +2 urls
                    </StatusBadge>
                  </span>
                </TooltipTrigger>
                <TooltipContent align="end" side="right">
                  <ul>
                    <li>
                      <a
                        href="https://nginxdemo.zaneops.local"
                        target="_blank"
                        className="underline text-link text-sm"
                      >
                        nginx-demo.zaneops.local
                      </a>
                    </li>
                    <li>
                      <a
                        href="https://nginxdemo.zaneops.local"
                        target="_blank"
                        className="underline text-link text-sm"
                      >
                        nginx-demo-docker.zaneops.local
                      </a>
                    </li>
                  </ul>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
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
            <div className="w-fit">
              <MultiSelect
                options={statuses}
                onValueChange={setSelectedStatuses}
                defaultValue={selectedStatuses}
                placeholder="Status"
                variant="inverted"
                animation={2}
                maxCount={3}
              />
            </div>
          </div>

          <div className="flex flex-col gap-4 mt-6">
            <h2 className="text-gray-400 text-sm">New</h2>
            <DeploymentCard
              commit_message="Update service"
              hash="1234"
              status="QUEUED"
              image="nginx:dmeo"
              queued_at={new Date()}
            />
            <DeploymentCard
              commit_message="Update service"
              hash="1234"
              status="PREPARING"
              image="nginx:dmeo"
              started_at={new Date("2024-09-18T23:05:49.741Z")}
              queued_at={new Date("2024-09-18T23:05:45.741Z")}
            />

            <h2 className="text-gray-400 text-sm">Current</h2>
            <DeploymentCard
              commit_message="Update service"
              hash="1234"
              status="HEALTHY"
              image="nginx:dmeo"
              finished_at={new Date()}
              started_at={new Date()}
              queued_at={new Date()}
            />
            <DeploymentCard
              commit_message="Update service"
              hash="1234"
              status="FAILED"
              image="nginx:dmeo"
              finished_at={new Date()}
              started_at={new Date()}
              queued_at={new Date()}
            />
            <DeploymentCard
              commit_message="Update service"
              hash="1234"
              status="SLEEPING"
              image="nginx:dmeo"
              finished_at={new Date()}
              started_at={new Date()}
              queued_at={new Date()}
            />

            <h2 className="text-gray-400 text-sm">Previous</h2>
            <DeploymentCard
              commit_message="Update service"
              hash="1234"
              status="CANCELLED"
              image="nginx:dmeo"
              queued_at={new Date()}
            />
            <DeploymentCard
              commit_message="Update service"
              hash="1234"
              status="REMOVED"
              image="nginx:dmeo"
              finished_at={new Date()}
              started_at={new Date()}
              queued_at={new Date()}
            />
            <DeploymentCard
              commit_message="Update service"
              hash="1234"
              status="REMOVED"
              image="nginx:dmeo"
              finished_at={new Date()}
              started_at={new Date()}
              queued_at={new Date()}
            />
            <DeploymentCard
              commit_message="Update service"
              hash="1234"
              status="REMOVED"
              image="nginx:dmeo"
              finished_at={new Date()}
              started_at={new Date()}
              queued_at={new Date()}
            />
          </div>

          <div className="flex justify-center items-center my-5">
            <Button variant="outline" className="w-1/3">
              Load More
            </Button>
          </div>

          {/* *
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

type DeploymentCardProps = {
  status:
    | "QUEUED"
    | "PREPARING"
    | "STARTING"
    | "RESTARTING"
    | "HEALTHY"
    | "UNHEALTHY"
    | "SLEEPING"
    | "FAILED"
    | "REMOVED"
    | "CANCELLED";
  started_at?: Date;
  finished_at?: Date;
  queued_at: Date;
  commit_message: string;
  image: string;
  hash: string;
};

function DeploymentCard({
  status,
  started_at,
  finished_at,
  queued_at,
  commit_message,
  image,
  hash
}: DeploymentCardProps) {
  const now = new Date();
  const [timeElapsed, setTimeElapsed] = React.useState(
    started_at ? Math.ceil((now.getTime() - started_at.getTime()) / 1000) : 0
  );

  React.useEffect(() => {
    if (started_at && !finished_at) {
      const timer = setInterval(() => {
        setTimeElapsed((prev) =>
          Math.ceil((new Date().getTime() - started_at.getTime()) / 1000)
        );
      }, 1000);

      return () => clearInterval(timer);
    }
  }, [started_at, finished_at]);

  return (
    <div
      className={cn(
        "flex border group  px-3 py-4 rounded-md  bg-opacity-10 justify-between items-center",
        {
          "border-blue-600 bg-blue-600":
            status === "STARTING" ||
            status === "RESTARTING" ||
            status === "PREPARING",
          "border-green-600 bg-green-600": status === "HEALTHY",
          "border-red-600 bg-red-600":
            status === "UNHEALTHY" || status === "FAILED",
          "border-gray-600 bg-gray-600":
            status === "REMOVED" ||
            status === "CANCELLED" ||
            status === "QUEUED",
          "border-yellow-600 bg-yellow-600": status === "SLEEPING"
        }
      )}
    >
      <div className="flex ">
        {/* First column */}
        <div className="w-[160px]">
          <h3 className="flex items-center gap-1 capitalize">
            <span
              className={cn("text-lg", {
                "text-blue-500":
                  status === "STARTING" ||
                  status === "RESTARTING" ||
                  status === "PREPARING",
                "text-green-500": status === "HEALTHY",
                "text-red-500": status === "UNHEALTHY" || status === "FAILED",
                "text-gray-500 dark:text-gray-400":
                  status === "REMOVED" ||
                  status === "CANCELLED" ||
                  status === "QUEUED",
                "text-yellow-500": status === "SLEEPING"
              })}
            >
              {capitalizeText(status)}
            </span>
            {Boolean(started_at && !finished_at) && (
              <Loader className="animate-spin" size={15} />
            )}
          </h3>
          <p className="text-sm text-gray-400 text-nowrap">
            {mergeTimeAgoFormatterAndFormattedDate(queued_at)}
          </p>
        </div>

        <div className="flex flex-col items-start">
          <h3>{commit_message}</h3>
          <div className="flex text-gray-400 gap-3 text-sm w-full items-center">
            <div className="gap-0.5 inline-flex items-center">
              <Timer size={15} />

              {!started_at && !finished_at && <span>-</span>}

              {started_at && finished_at && (
                <span>
                  {(finished_at.getTime() - started_at.getTime()) / 1000}s
                </span>
              )}

              {started_at && !finished_at && (
                <span>{formatElapsedTime(timeElapsed)}</span>
              )}
            </div>
            <div className="gap-1 inline-flex items-center">
              <Container size={15} />
              <span>{image}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Button
          asChild
          variant="ghost"
          className={cn("border hover:bg-inherit", {
            "border-blue-600":
              status === "STARTING" ||
              status === "RESTARTING" ||
              status === "PREPARING",
            "border-green-600": status === "HEALTHY",
            "border-red-600": status === "UNHEALTHY" || status === "FAILED",
            "border-gray-600 opacity-0 group-hover:opacity-100 transition-opacity ease-in duration-150":
              status === "REMOVED" ||
              status === "CANCELLED" ||
              status === "QUEUED",
            "border-yellow-600": status === "SLEEPING"
          })}
        >
          <Link to={`deployments/${hash}/logs`}>View logs</Link>
        </Button>

        <Menubar className="border-none h-auto md:block hidden w-fit">
          <MenubarMenu>
            <MenubarTrigger
              className="flex justify-center items-center gap-2"
              asChild
            >
              <Button variant="ghost" className="px-2 hover:bg-inherit">
                <EllipsisVertical />
              </Button>
            </MenubarTrigger>
            <MenubarContent className="border min-w-0 mx-9  border-border">
              <MenubarContentItem icon={Eye} text="Details" />
              <MenubarContentItem icon={ScrollText} text="View logs" />
              <MenubarContentItem icon={Redo2} text="Redeploy" />
              <MenubarContentItem icon={Ban} text="Cancel" />
            </MenubarContent>
          </MenubarMenu>
        </Menubar>
      </div>
    </div>
  );
}
