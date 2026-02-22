import { useQuery } from "@tanstack/react-query";
import { Maximize2Icon, Minimize2Icon } from "lucide-react";
import * as React from "react";
import { Navigate, href, useSearchParams } from "react-router";
import type { ComposeStackTask } from "~/api/types";
import { TaskWithContainerSelectItem } from "~/components/task-with-container-select-item";
import { Terminal } from "~/components/terminal";
import { Button } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue
} from "~/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { composeStackQueries } from "~/lib/queries";
import { cn } from "~/lib/utils";
import type { Route } from "./+types/compose-stack-service-terminal";

export default function ComposeStackServiceTerminalPage({
  params,
  matches: {
    2: { loaderData }
  }
}: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [counter, setCounter] = React.useState(0);
  const { data: stack } = useQuery({
    ...composeStackQueries.single({
      project_slug: params.projectSlug,
      stack_slug: params.composeStackSlug,
      env_slug: params.envSlug
    }),
    initialData: loaderData.stack
  });

  const serviceFound = Object.entries(stack.services).find(
    ([name]) => name === params.serviceSlug
  );

  if (!serviceFound) {
    return (
      <Navigate
        to={href(
          "/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug",
          params
        )}
      />
    );
  }

  const shellCmd = searchParams.get("shellCmd")?.toString() ?? undefined;
  const user = searchParams.get("user")?.toString() ?? undefined;
  const selectedContainerId =
    searchParams.get("container_id")?.toString() ?? undefined;

  const isMaximized = searchParams.get("isMaximized") === "true";
  const webSocketScheme = window.location.protocol === "http:" ? "ws" : "wss";

  const [, service] = serviceFound;

  const tasks = service.tasks
    .filter((t) => t.container_id !== null)
    .toSorted((tA, tB) => tB.version - tA.version) as Array<
    Omit<ComposeStackTask, "container_id"> & { container_id: string }
  >;

  const running = tasks.filter(
    (task) =>
      task.desired_status === "running" || task.desired_status === "complete"
  );

  const old = tasks.filter(
    (task) =>
      task.desired_status !== "running" && task.desired_status !== "complete"
  );

  const taskFound = tasks.find((t) => t.container_id === selectedContainerId);

  let apiHost = window.location.host;

  if (apiHost.includes("localhost:5173")) {
    apiHost = "localhost:8000";
  }
  const baseWebSocketURL = taskFound
    ? `${webSocketScheme}://${apiHost}/ws/compose-stack-terminal/${params.projectSlug}/${params.envSlug}/${params.composeStackSlug}/${params.serviceSlug}/${taskFound.container_id}`
    : "";

  const DEFAULT_SHELLS = [
    "/bin/sh",
    "/bin/bash",
    "/usr/bin/fish",
    "/usr/bin/zsh",
    "/usr/bin/ksh",
    "/usr/bin/tcsh"
  ];

  return (
    <div
      className={cn(
        "flex flex-col pt-5 overflow-hidden",
        isMaximized && "fixed inset-0 bg-background z-100 p-0 w-full"
      )}
    >
      <form
        action={(formData) => {
          const user = formData.get("user")?.toString().trim();
          const shellCmd = formData.get("shellCmd")?.toString().trim();
          if (user) {
            searchParams.set("user", user);
          } else {
            searchParams.delete("user");
          }
          if (shellCmd) {
            searchParams.set("shellCmd", shellCmd);
          }
          setSearchParams(searchParams);
          setCounter((c) => c + 1);
        }}
        className={cn(
          "p-2.5 flex items-center gap-2 bg-muted rounded-none",
          shellCmd && !isMaximized && "rounded-t-md"
        )}
      >
        <TooltipProvider>
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                onClick={() => {
                  searchParams.set("isMaximized", (!isMaximized).toString());
                  setSearchParams(searchParams, { replace: true });
                }}
              >
                <span className="sr-only">
                  {isMaximized ? "Minimize" : "Maximize"}
                </span>
                {isMaximized ? (
                  <Minimize2Icon size={15} />
                ) : (
                  <Maximize2Icon size={15} />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent className="max-w-64 text-balance z-200">
              {isMaximized ? "Minimize" : "Maximize"}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>

        <Select
          name="container_id"
          value={taskFound?.container_id ?? "<none>"}
          onValueChange={(value) => {
            searchParams.delete("container_id");
            if (value !== "<none>") {
              searchParams.set("container_id", value);
              if (!shellCmd) {
                searchParams.set("shellCmd", "/bin/sh");
              }
            } else {
              searchParams.delete("shellCmd");
            }
            setSearchParams(searchParams);
          }}
        >
          <SelectTrigger className="w-54  [&_[data-empty]]:!text-grey placeholder-shown:text-grey">
            <SelectValue placeholder="select replica" className="text-grey" />
          </SelectTrigger>
          <SelectContent className="border border-border text-sm">
            <SelectItem value="<none>" className="text-grey">
              <span data-empty>(Select a replica)</span>
            </SelectItem>

            {running.length > 0 && (
              <SelectGroup>
                <SelectLabel>Current</SelectLabel>
                {running.map((task) => (
                  <TaskWithContainerSelectItem
                    container_id={task.container_id}
                    status={task.status}
                    key={task.id}
                  />
                ))}
              </SelectGroup>
            )}
            {old.length > 0 && (
              <SelectGroup>
                <SelectLabel>Previous</SelectLabel>

                {old.map((task) => (
                  <TaskWithContainerSelectItem
                    container_id={task.container_id}
                    status={task.status}
                    key={task.id}
                  />
                ))}
              </SelectGroup>
            )}
          </SelectContent>
        </Select>

        <Select
          name="shellCmd"
          value={shellCmd ?? "/bin/sh"}
          onValueChange={(value) => {
            searchParams.set("shellCmd", value);
            setSearchParams(searchParams);
          }}
        >
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Select a shell" />
          </SelectTrigger>
          <SelectContent className="border border-border z-200" side="top">
            {DEFAULT_SHELLS.map((shell) => (
              <SelectItem key={shell} value={shell}>
                {shell}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <label htmlFor="user" className="sr-only">
          user
        </label>
        <Input
          placeholder="user (optional)"
          id="user"
          className="max-w-44"
          name="user"
          defaultValue={searchParams.get("user")}
        />
        <Button type="submit" variant="outline">
          {shellCmd ? "Reconnect" : "Connect"}
        </Button>
      </form>

      <div
        className={cn(
          "flex-1 py-2",
          shellCmd && taskFound?.container_id && "bg-terminal px-2"
        )}
      >
        {shellCmd && taskFound?.container_id ? (
          <Terminal
            baseWebSocketURL={baseWebSocketURL}
            shellCommand={shellCmd}
            key={counter}
            shellUser={user}
            className={cn(
              isMaximized ? "h-[calc(100vh-(var(--spacing)*20))]" : "h-[50dvh]"
            )}
          />
        ) : (
          <p className="italic text-grey border-b border-border pb-2">
            -- Select a replica to access the terminal --
          </p>
        )}
      </div>
    </div>
  );
}
