import * as React from "react";
import { Terminal as XTermTerminal } from "xterm";
import { FitAddon } from "xterm-addon-fit";
import type { Route } from "./+types/deployment-terminal";
import "xterm/css/xterm.css";
import { Maximize2Icon, Minimize2Icon } from "lucide-react";
import { useSearchParams } from "react-router";
import { Terminal } from "~/components/terminal";
import { Button } from "~/components/ui/button";
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
  const [shell, setShell] = React.useState("/bin/sh");
  const [websocketURL, setWebsocketURL] = React.useState<string | null>(null);
  const [counter, setCounter] = React.useState(0);
  const [searchParams, setSearchParams] = useSearchParams();

  const isMaximized = searchParams.get("isMaximized") === "true";
  let currentHost = window.location.host;
  let webSocketScheme = window.location.protocol === "http:" ? "ws" : "wss";

  if (currentHost.includes("localhost:5173")) {
    currentHost = "localhost:8000";
  }

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
        "flex flex-col pt-5",
        isMaximized && "fixed inset-0 bg-background z-100 p-0 w-full"
      )}
    >
      <header
        className={cn(
          "p-2.5 flex items-center gap-2 bg-muted rounded-none",
          websocketURL && !isMaximized && "rounded-t-md"
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
        <Select value={shell} onValueChange={(value) => setShell(value)}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Select Shell" />
          </SelectTrigger>
          <SelectContent className="border border-border z-200" side="top">
            {DEFAULT_SHELLS.map((shell) => (
              <SelectItem key={shell} value={shell}>
                {shell}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          variant="outline"
          onClick={() => {
            setWebsocketURL(
              `${webSocketScheme}://${currentHost}/ws/webshell/${params.projectSlug}/${params.envSlug}/${params.serviceSlug}/${params.deploymentHash}`
            );
            setCounter((c) => c + 1);
          }}
        >
          {websocketURL ? "Reconnect" : "Connect"}
        </Button>
      </header>

      <div className={cn("flex-1 py-2", websocketURL && "bg-black px-2")}>
        {websocketURL ? (
          <Terminal
            baseWebSocketURL={websocketURL}
            shellCommand={shell}
            key={counter}
            className={cn(!isMaximized && "h-[50dvh]")}
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
