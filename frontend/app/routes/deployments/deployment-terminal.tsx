import * as React from "react";
import { Terminal as XTermTerminal } from "xterm";
import { FitAddon } from "xterm-addon-fit";
import type { Route } from "./+types/deployment-terminal";
import "xterm/css/xterm.css";
import { Maximize2Icon, Minimize2Icon } from "lucide-react";
import { useSearchParams } from "react-router";
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
            <TooltipContent className="max-w-64 text-balance">
              {isMaximized ? "Minimize" : "Maximize"}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <Select value={shell} onValueChange={(value) => setShell(value)}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Select Shell" />
          </SelectTrigger>
          <SelectContent className="border border-border" side="top">
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
              `ws://${currentHost}/ws/webshell/${params.projectSlug}/${params.envSlug}/${params.serviceSlug}/${params.deploymentHash}`
            );
            setCounter((c) => c + 1);
          }}
        >
          {websocketURL ? "Reconnect" : "Connect"}
        </Button>
      </header>

      <div
        className={cn(
          "flex-1 min-h-[50dvh] py-2",
          websocketURL && "bg-black px-2"
        )}
      >
        {websocketURL ? (
          <Terminal
            wsUrl={websocketURL}
            shellCommand={shell}
            key={counter}
            onDisconnect={() => setWebsocketURL(null)}
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

type TerminalProps = {
  shellCommand?: string;
  wsUrl: string;
  onDisconnect?: () => void;
};

function Terminal({
  shellCommand = "/bin/sh",
  wsUrl,
  onDisconnect
}: TerminalProps) {
  const terminalRef = React.useRef<HTMLDivElement>(null);
  const term = React.useRef<XTermTerminal>(null);
  const fitAddon = React.useRef<FitAddon>(new FitAddon());
  const socketRef = React.useRef<WebSocket | null>(null);

  // Send terminal size to backend over WebSocket
  const sendResize = () => {
    if (!term.current || !socketRef.current) return;
    const cols = term.current.cols;
    const rows = term.current.rows;
    const resizeMessage = JSON.stringify({ type: "resize", cols, rows });
    if (socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(resizeMessage);
    }
  };

  React.useEffect(() => {
    if (!terminalRef.current) return;

    // 1. Initialize terminal + fit addon
    term.current = new XTermTerminal({
      cursorBlink: true,
      cols: 80,
      rows: 24
    });
    fitAddon.current = new FitAddon();
    term.current.loadAddon(fitAddon.current);

    // 2. Attach terminal to DOM
    term.current.open(terminalRef.current);
    fitAddon.current.fit();

    // 3. Build WebSocket URL with query params
    const params = new URLSearchParams();
    params.set("cmd", encodeURIComponent(shellCommand));
    const url = `${wsUrl}/?${params.toString()}`;

    // 4. Connect
    socketRef.current = new WebSocket(url);

    socketRef.current.onmessage = (evt) => {
      if (term.current) {
        term.current.write(evt.data);
      }
    };

    socketRef.current.onopen = (evt) => {
      if (term.current) {
        sendResize();
      }
    };

    socketRef.current.onerror = (err) => {
      if (term.current) {
        term.current.writeln(`\x1b[31mWebSocket error\x1b[0m`);
      }
    };

    socketRef.current.onclose = () => {
      if (term.current) {
        term.current.writeln(`\x1b[33mDisconnected\x1b[0m`);
      }
    };

    // 5. When user types, send to container
    term.current.onData((data) => {
      if (socketRef.current?.readyState === WebSocket.OPEN && term.current) {
        console.log({
          data
        });
        // term.current.write(data);
        socketRef.current.send(data);
      }
    });

    // 6. Handle window resize
    const handleResize = () => {
      fitAddon.current.fit();
      sendResize();
    };
    window.addEventListener("resize", handleResize);

    // Cleanup on unmount
    return () => {
      window.removeEventListener("resize", handleResize);
      socketRef.current?.close();
      term.current?.dispose();
    };
  }, [shellCommand, wsUrl, onDisconnect]);

  return <div ref={terminalRef} className="w-full h-full" />;
}
