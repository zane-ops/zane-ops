import { useQuery } from "@tanstack/react-query";
import { useLocalStorage } from "@uidotdev/usehooks";
import { Maximize2Icon, Minimize2Icon } from "lucide-react";
import * as React from "react";
import { useSearchParams } from "react-router";
import { Terminal } from "~/components/terminal";
import { Button } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetLabel,
  FieldSetSelect
} from "~/components/ui/fieldset";
import {
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
import { createDevLogger } from "~/lib/logger";
import { swarmQueries } from "~/lib/queries";
import { cn, metaTitle } from "~/lib/utils";
import type { Route } from "./+types/swarm-node-console";

export function meta() {
  return [metaTitle("Server Console")] satisfies ReturnType<Route.MetaFunction>;
}

const logger = createDevLogger(import.meta.url);

export default function SwarmNodeConsolePage({
  params,
  matches: {
    "3": { loaderData }
  }
}: Route.ComponentProps) {
  const { data: node } = useQuery({
    ...swarmQueries.singleNode(params.serverId),
    initialData: loaderData.node
  });

  const [searchParams, setSearchParams] = useSearchParams();
  const keyIdInSearch = searchParams.get("ssh_key_id")?.toString().trim();

  const [lastKeyId, setLastKeyId] = useLocalStorage<string | null>(
    `server_console_last_ssh_key_id_for_${node.id}`,
    keyIdInSearch ?? null
  );

  const [counter, setCounter] = React.useState(0);

  const keyId = keyIdInSearch ?? lastKeyId;
  const [selectedKey, setSelectedKey] = React.useState(keyId);
  const isMaximized = searchParams.get("isMaximized") === "true";

  logger.scope("SwarmNodeConsolePage").info({ selectedKey });

  return (
    <section className="flex flex-col gap-4">
      <h3 className="text-grey">Connect via SSH to your server.</h3>

      <div
        className={cn(
          "flex flex-col overflow-hidden",
          isMaximized && "fixed inset-0 bg-background z-100 p-0 w-full"
        )}
      >
        <form
          action={(formData) => {
            const keyId = formData.get("ssh_key_id")?.toString().trim();
            if (keyId) {
              searchParams.set("ssh_key_id", keyId);
              setLastKeyId(keyId);
            }

            logger.scope("form.action").info({
              'formData.get("ssh_key_id")': keyId,
              'searchParams.get("ssh_key_id")': searchParams.get("ssh_key_id")
            });
            setSearchParams(searchParams);
            setCounter((c) => c + 1); // force rerender
          }}
          method="get"
          className={cn(
            "flex items-end gap-2",
            "p-2.5 flex items-center gap-2 bg-muted rounded-none",
            keyId && !isMaximized && "rounded-t-md"
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

          {/*
             This is to mitigate a behavior with React 
             which resets the value of inputs after a succesfull `action`
            */}
          <input
            type="hidden"
            name="ssh_key_id"
            value={selectedKey ?? undefined}
          />

          <FieldSet name="" className="flex flex-col gap-1.5">
            <FieldSetLabel htmlFor="ssh_key_id" className="sr-only">
              SSH Key
            </FieldSetLabel>
            <FieldSetSelect
              defaultValue={selectedKey ?? undefined}
              value={selectedKey ?? undefined}
              onValueChange={setSelectedKey}
            >
              <SelectTrigger id="ssh_key_id" className="w-56">
                <SelectValue placeholder="Select a Key" />
              </SelectTrigger>
              <SelectContent className="z-200">
                {node.ssh_keys.length === 0 && (
                  <SelectItem disabled value="none">
                    No SSH keys found
                  </SelectItem>
                )}
                {node.ssh_keys.map((ssh) => (
                  <SelectItem key={ssh.id} value={ssh.id.toString()}>
                    {ssh.name} ({ssh.user})
                  </SelectItem>
                ))}
              </SelectContent>
            </FieldSetSelect>
          </FieldSet>

          <Button type="submit" variant="outline">
            {keyId ? "Reconnect" : "Connect"}
          </Button>
        </form>

        <div className={cn("flex-1 py-2", keyId && "bg-terminal px-2")}>
          {keyId ? (
            <ServerTerminal
              keyId={keyId}
              key={counter}
              nodeId={node.id}
              className={cn(
                isMaximized
                  ? "h-[calc(100vh-(var(--spacing)*20))]"
                  : "h-[48dvh]"
              )}
            />
          ) : (
            <p className="italic text-grey border-b border-border pb-2">
              -- Select a SSH key to access the terminal --
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

function ServerTerminal({
  keyId,
  nodeId,
  className
}: { keyId: string; nodeId: string; className?: string }) {
  const webSocketScheme = window.location.protocol === "http:" ? "ws" : "wss";
  let apiHost = window.location.host;

  if (apiHost.includes("localhost:5173")) {
    apiHost = "localhost:8000";
  }
  const baseWebSocketURL = `${webSocketScheme}://${apiHost}/ws/server-ssh/${nodeId}/${keyId}`;
  return <Terminal baseWebSocketURL={baseWebSocketURL} className={className} />;
}
