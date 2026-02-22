import {
  ChevronRightIcon,
  ClockArrowUpIcon,
  ClockPlusIcon,
  ContainerIcon,
  EllipsisVerticalIcon,
  HashIcon,
  Layers2Icon,
  LoaderIcon,
  LogOutIcon,
  MessageCircleMoreIcon,
  ScanTextIcon,
  TerminalIcon
} from "lucide-react";
import React from "react";
import { Link, useNavigate } from "react-router";
import type { ComposeStackTask } from "~/api/types";
import { Code } from "~/components/code";
import { CopyButton } from "~/components/copy-button";
import type { StatusBadgeColor } from "~/components/status-badge";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
import { Button } from "~/components/ui/button";
import { Card } from "~/components/ui/card";
import {
  Menubar,
  MenubarContent,
  MenubarContentItem,
  MenubarMenu,
  MenubarTrigger
} from "~/components/ui/menubar";
import { cn } from "~/lib/utils";
import {
  getDockerImageIconURL,
  mergeTimeAgoFormatterAndFormattedDate
} from "~/utils";

export const TASK_STATUS_COLOR_MAP = {
  new: "gray",
  pending: "gray",
  assigned: "blue",
  accepted: "blue",
  ready: "blue",
  preparing: "blue",
  starting: "blue",
  running: "green",
  complete: "yellow",
  failed: "red",
  shutdown: "gray",
  rejected: "red",
  orphaned: "red",
  remove: "gray"
} as const satisfies Record<ComposeStackTask["status"], StatusBadgeColor>;

export type ComposeStackServiceReplicaCardProps = {
  task: ComposeStackTask;
  isPrevious?: boolean;
};

export function ComposeStackServiceReplicaCard({
  task,
  isPrevious = false
}: ComposeStackServiceReplicaCardProps) {
  const color = TASK_STATUS_COLOR_MAP[task.status];

  const [iconNotFound, setIconNotFound] = React.useState(false);
  const [accordionValue, setAccordionValue] = React.useState(
    color === "red" && !isPrevious ? `task-${task.id}` : ""
  );
  const navigate = useNavigate();

  const image = task.image;
  const isLoading = color === "blue";

  let iconSrc: string | null = null;
  if (image) {
    iconSrc = getDockerImageIconURL(image);
  }

  const [imageVersion, imageSha] = task.image.split("@");

  const [prefix, slot, taskId] = task.name.split(".");

  return (
    <Card
      className={cn(
        "border border-border p-1 shadow-none group relative flex flex-col gap-1",
        {
          "border-emerald-500": color === "green",
          "border-red-600": color === "red",
          "border-amber-500": color === "yellow",
          "border-gray-600": color === "gray",
          "border-link": color === "blue",
          "border-dashed": isPrevious
        }
      )}
    >
      <div
        className={cn(
          "rounded-md py-2 pl-4 pr-3 flex flex-col  items-start gap-0 font-normal",
          "md:flex-row md:items-center md:gap-6",
          "relative",
          {
            "bg-emerald-400/10 dark:bg-emerald-600/20 has-data-[logs-link]:hover:bg-emerald-300/30":
              color === "green",
            "bg-red-600/10 has-data-[logs-link]:hover:bg-red-600/20":
              color === "red",
            "bg-yellow-400/10 dark:bg-yellow-600/10 has-data-[logs-link]:hover:bg-yellow-400/20":
              color === "yellow",
            "bg-gray-600/10 has-data-[logs-link]:hover:bg-gray-600/20":
              color === "gray",
            "bg-blue-500/10 has-data-[logs-link]:hover:bg-blue-500/20":
              color === "blue"
          }
        )}
      >
        {/* Status */}
        <div
          className={cn(
            "min-w-26 flex flex-row items-end justify-center h-full gap-2 pt-2 pb-6 md:pt-0 md:pb-0",
            "md:flex-col md:items-start"
          )}
        >
          <div
            className={cn(
              "relative top-0.5 rounded-md text-link px-2  inline-flex gap-1 items-center py-0.5",
              {
                "bg-emerald-400/30 dark:bg-emerald-600/20 text-green-600  dark:text-emerald-400":
                  color === "green",
                "bg-red-600/25 text-red-700 dark:text-red-400": color === "red",
                "bg-yellow-400/30 dark:bg-yellow-600/20 text-amber-700 dark:text-yellow-300":
                  color === "yellow",
                "bg-gray-600/20 dark:bg-gray-600/60 text-card-foreground":
                  color === "gray",
                "bg-blue-500/30 text-link": color === "blue"
              }
            )}
          >
            <code className="text-sm">
              {(task.status === "remove"
                ? "removed"
                : task.status
              ).toUpperCase()}
            </code>
            {isLoading && (
              <LoaderIcon className="animate-spin flex-none" size={15} />
            )}
          </div>

          <time dateTime={task.updated_at} className="text-grey text-sm">
            {mergeTimeAgoFormatterAndFormattedDate(task.updated_at)}
          </time>
        </div>

        {/* Name & image */}
        <div className="flex flex-col gap-2 grow">
          <div className="flex gap-1 items-center">
            <HashIcon className="size-4 flex-none text-grey md:hidden" />
            {task.container_id ? (
              <Link
                to={`./runtime-logs?container_id=${task.container_id}`}
                data-logs-link
                className="inline break-all text-sm text-start after:absolute after:inset-0"
              >
                <span className="text-grey hidden md:inline">
                  {prefix}.{slot}.
                </span>
                <span>{taskId}</span>
              </Link>
            ) : (
              <span className="inline text-sm text-start break-all">
                <span className="text-grey hidden md:inline">
                  {prefix}.{slot}.
                </span>
                <span>{taskId}</span>
              </span>
            )}
          </div>

          <div className="inline-flex items-start gap-1">
            {iconSrc && !iconNotFound ? (
              <img
                src={iconSrc}
                onError={() => setIconNotFound(true)}
                alt={`Logo for ${image}`}
                className="size-4 md:size-3 flex-none object-center object-contain rounded-sm relative top-1"
              />
            ) : (
              <ContainerIcon className="flex-none size-3 relative top-0.5" />
            )}
            <small className="break-all inline whitespace-normal text-start text-xs">
              {imageVersion}
              <span className="text-grey">:{imageSha}</span>
            </small>
          </div>
        </div>

        {task.container_id && (
          <div className="flex items-center gap-2 static md:relative z-10">
            {/* View logs button */}
            <Button
              asChild
              variant="ghost"
              size="sm"
              className={cn("border hover:bg-inherit hidden md:inline-flex", {
                "border-emerald-500": color === "green",
                "border-gray-600": color === "gray",
                "border-amber-500": color === "yellow",
                "border-link": color === "blue",
                "border-red-600": color === "red"
              })}
            >
              <Link to={`./runtime-logs?container_id=${task.container_id}`}>
                View logs
              </Link>
            </Button>

            <Menubar className="border-none h-auto w-fit">
              <MenubarMenu>
                <MenubarTrigger
                  className={cn(
                    "flex justify-center items-center gap-2 md:static",
                    "absolute z-10 top-2 right-4"
                  )}
                  asChild
                >
                  <Button
                    variant="ghost"
                    size="sm"
                    className="px-1.5 py-1 hover:bg-inherit"
                  >
                    <EllipsisVerticalIcon className="flex-none size-4" />
                  </Button>
                </MenubarTrigger>
                <MenubarContent
                  side="bottom"
                  align="center"
                  className="border min-w-0 mx-9 border-border"
                >
                  <MenubarContentItem
                    icon={ScanTextIcon}
                    text="View logs"
                    onClick={() =>
                      navigate(
                        `./runtime-logs?container_id=${task.container_id}`
                      )
                    }
                  />

                  <MenubarContentItem
                    icon={TerminalIcon}
                    text="Terminal"
                    onClick={() => {
                      const sp = new URLSearchParams({
                        container_id: task.container_id!,
                        shellCmd: "/bin/sh"
                      });
                      navigate(`./terminal?${sp.toString()}`);
                    }}
                  />
                </MenubarContent>
              </MenubarMenu>
            </Menubar>
          </div>
        )}
      </div>

      <Accordion
        type="single"
        collapsible
        value={accordionValue}
        onValueChange={(state) => {
          setAccordionValue(state);
        }}
        className="w-full p-0 border-none"
      >
        <AccordionItem
          value={`task-${task.id}`}
          className="w-full p-0 font-normal border-none"
        >
          <AccordionTrigger
            className={cn(
              "rounded-md py-1 px-4 flex items-center gap-6 font-normal cursor-pointer",
              "data-[state=open]:rounded-b-none [&[data-state=open]_svg]:rotate-90",
              {
                "bg-emerald-400/10 dark:bg-emerald-600/20 hover:bg-emerald-300/30":
                  color === "green",
                "bg-red-600/10 hover:bg-red-600/20": color === "red",
                "bg-yellow-400/10 dark:bg-yellow-600/10 ": color === "yellow",
                "bg-gray-600/10 hover:bg-gray-600/20": color === "gray",
                "bg-blue-500/10 hover:bg-blue-500/20": color === "blue"
              }
            )}
          >
            <div className="flex w-full items-center">
              <span className="text-sm">details</span>
              <ChevronRightIcon className="size-4" />
            </div>
          </AccordionTrigger>

          <AccordionContent
            className={cn(
              "flex items-center gap-6 px-3 py-3",
              "w-full border-none rounded-b-md ",
              {
                "bg-emerald-400/10 dark:bg-emerald-600/20 ": color === "green",
                "bg-red-600/10 ": color === "red",
                "bg-yellow-400/10 dark:bg-yellow-600/10 ": color === "yellow",
                "bg-gray-600/10": color === "gray",
                "bg-blue-500/10": color === "blue"
              }
            )}
          >
            <div className="flex flex-col w-full">
              {/* Task message */}
              <div className="text-sm inline-grid items-stretch gap-2 grid-cols-[auto_1fr]">
                <div className="w-4 hidden md:flex flex-col items-center gap-2 h-full self-stretch relative top-1">
                  <MessageCircleMoreIcon className="size-4 flex-none text-grey" />
                  <div className="h-full  bg-grey/50 w-px min-h-5 grow flex-1 mb-1"></div>
                </div>

                <div className="flex flex-col gap-0 w-full">
                  <span>Message</span>
                  <span
                    className={cn(
                      "w-full py-2 my-1 break-all rounded-md px-2",
                      {
                        "bg-emerald-400/30 dark:bg-emerald-600/20 text-green-700  dark:text-emerald-400":
                          color === "green",
                        "bg-red-600/25 text-red-700 dark:text-red-400":
                          color === "red",
                        "bg-yellow-400/30 dark:bg-yellow-600/20 text-amber-700 dark:text-yellow-300":
                          color === "yellow",
                        "bg-gray-600/20 dark:bg-gray-600/60 text-gray":
                          color === "gray",
                        "bg-blue-500/30 text-link dark:text-blue-100":
                          color === "blue"
                      }
                    )}
                  >
                    {task.message}
                  </span>
                </div>
              </div>
              {/* container ID */}
              <div className="text-sm inline-grid items-start gap-2 grid-cols-[auto_1fr]">
                <div className="w-4 hidden md:flex flex-col items-center gap-2 relative top-1 h-full self-stretch">
                  <ContainerIcon className="size-4 flex-none text-grey" />
                  <div className="min-h-5 h-full bg-grey/50 w-px mb-2"></div>
                </div>

                <div className="flex flex-col relative top-0.5">
                  <span>Container ID</span>
                  <p className="text-grey">
                    {task.container_id === null ? (
                      <pre className="font-mono">{`<empty>`}</pre>
                    ) : (
                      <CopyButton
                        className="text-grey p-0 inline-flex w-fit bg-inherit hover:bg-inherit"
                        label={task.container_id}
                        value={task.container_id}
                        showLabel
                      />
                    )}
                  </p>
                </div>
              </div>

              {/* Task ID */}
              <div className="text-sm inline-grid items-start gap-2 grid-cols-[auto_1fr]">
                <div className="w-4 hidden md:flex flex-col items-center gap-2 relative top-1 h-full self-stretch">
                  <Layers2Icon className="size-4 flex-none text-grey" />
                  <div className="min-h-5 h-full bg-grey/50 w-px mb-2"></div>
                </div>

                <div className="flex flex-col relative top-0.5">
                  <span>Replica ID</span>
                  <CopyButton
                    className="text-grey p-0 inline-flex w-fit bg-inherit hover:bg-inherit"
                    label={task.id}
                    value={task.id}
                    showLabel
                  />
                </div>
              </div>

              {/* Task Created At */}
              <div className="text-sm inline-grid items-start gap-2 grid-cols-[auto_1fr]">
                <div className="w-4 hidden md:flex flex-col items-center gap-2 relative top-1 h-full self-stretch">
                  <ClockPlusIcon className="size-4 flex-none text-grey" />
                  <div className="min-h-5 h-full bg-grey/50 w-px mb-2"></div>
                </div>

                <div className="flex flex-col relative top-0.5">
                  <span>Created</span>
                  <span className="text-grey py-2">
                    {mergeTimeAgoFormatterAndFormattedDate(task.created_at)}
                  </span>
                </div>
              </div>

              {/* Task Updated At */}
              <div className="text-sm inline-grid items-start gap-2 grid-cols-[auto_1fr]">
                <div className="w-4 hidden md:flex flex-col items-center gap-2 relative top-1 h-full self-stretch">
                  <ClockArrowUpIcon className="size-4 flex-none text-grey" />
                  <div className="min-h-5 h-full bg-grey/50 w-px mb-2"></div>
                </div>

                <div className="flex flex-col relative top-0.5">
                  <span>Updated</span>
                  <span className="text-grey py-2">
                    {mergeTimeAgoFormatterAndFormattedDate(task.updated_at)}
                  </span>
                </div>
              </div>

              {/* Slot */}
              <div className="text-sm inline-grid items-center gap-2 grid-cols-[auto_1fr]">
                <Layers2Icon className="size-4 flex-none text-grey" />
                <div className="flex items-center gap-2">
                  <span>Replica number</span>
                  <Code>{task.slot}</Code>
                </div>
              </div>

              {/* Exit code */}
              <div className="text-sm inline-grid items-center gap-2 grid-cols-[auto_1fr]">
                <LogOutIcon className="size-4 flex-none text-grey" />

                <div className="flex gap-2 items-center">
                  <span>Exit Code:</span>
                  <Code className={cn(task.exit_code === null && "text-grey")}>
                    {task.exit_code === null ? "<empty>" : task.exit_code}
                  </Code>
                </div>
              </div>
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </Card>
  );
}
