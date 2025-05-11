import * as React from "react";
import type { Route } from "./+types/deployment-terminal";
import "xterm/css/xterm.css";
import { Maximize2Icon, Minimize2Icon } from "lucide-react";
import { useSearchParams } from "react-router";
import { Terminal } from "~/components/terminal";
import { Button } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "~/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { cn } from "~/lib/utils";

export default function DeploymentTerminalPage({
  params
}: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [counter, setCounter] = React.useState(0);

  const shellCmd = searchParams.get("shellCmd")?.toString() ?? undefined;
  const user = searchParams.get("user")?.toString() ?? undefined;

  const isMaximized = searchParams.get("isMaximized") === "true";
  let webSocketScheme = window.location.protocol === "http:" ? "ws" : "wss";
  let apiHost = window.location.host;

  if (apiHost.includes("localhost:5173")) {
    apiHost = "localhost:8000";
  }
  const baseWebSocketURL = `${webSocketScheme}://${apiHost}/ws/deployment-terminal/${params.projectSlug}/${params.envSlug}/${params.serviceSlug}/${params.deploymentHash}`;

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

      <div className={cn("flex-1 py-2", shellCmd && "bg-black px-2")}>
        {shellCmd ? (
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
            -- Connect to the container to access the terminal --
          </p>
        )}
      </div>
    </div>
  );
}
