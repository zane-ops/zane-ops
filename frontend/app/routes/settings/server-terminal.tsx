import { useQuery } from "@tanstack/react-query";
import { Maximize2Icon, Minimize2Icon } from "lucide-react";
import * as React from "react";
import { Form, useSearchParams } from "react-router";
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
import { Separator } from "~/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { sshKeysQueries } from "~/lib/queries";
import { cn } from "~/lib/utils";
import { queryClient } from "~/root";
import { metaTitle } from "~/utils";
import type { Route } from "./+types/server-terminal";

export function meta() {
  return [metaTitle("Terminal")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader() {
  const sshKeys = await queryClient.ensureQueryData(sshKeysQueries.list);
  return { sshKeys };
}

export default function ServerTerminalPage({
  loaderData
}: Route.ComponentProps) {
  const { data: sshKeys } = useQuery({
    ...sshKeysQueries.list,
    initialData: loaderData.sshKeys
  });

  const [searchParams, setSearchParams] = useSearchParams();
  const [counter, setCounter] = React.useState(0);

  const keySlug = searchParams.get("ssh_key_slug")?.toString().trim();
  const isMaximized = searchParams.get("isMaximized") === "true";

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Server Console</h2>
      </div>
      <Separator />
      <h3>Connect via SSH to your server.</h3>

      <div
        className={cn(
          "flex flex-col overflow-hidden",
          isMaximized && "fixed inset-0 bg-background z-100 p-0 w-full"
        )}
      >
        <form
          action={(formData) => {
            const keySlug = formData.get("ssh_key_slug")?.toString().trim();
            if (keySlug) {
              searchParams.set("ssh_key_slug", keySlug);
            }
            setSearchParams(searchParams);
            setCounter((c) => c + 1);
          }}
          method="get"
          className={cn(
            "flex items-end gap-2",
            "p-2.5 flex items-center gap-2 bg-muted rounded-none",
            keySlug && !isMaximized && "rounded-t-md"
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
          <FieldSet name="slug" className="flex flex-col gap-1.5">
            <FieldSetLabel htmlFor="ssh_key_slug" className="sr-only">
              SSH Key
            </FieldSetLabel>
            <FieldSetSelect name="ssh_key_slug" defaultValue={keySlug}>
              <SelectTrigger id="ssh_key_slug" className="w-56">
                <SelectValue placeholder="Select a Key" />
              </SelectTrigger>
              <SelectContent className="z-200">
                {sshKeys.length === 0 && (
                  <SelectItem disabled value="none">
                    No SSH keys found
                  </SelectItem>
                )}
                {sshKeys.map((ssh) => (
                  <SelectItem key={ssh.id} value={ssh.slug}>
                    {ssh.slug} ({ssh.user})
                  </SelectItem>
                ))}
              </SelectContent>
            </FieldSetSelect>
          </FieldSet>

          <Button type="submit" variant="outline">
            {keySlug ? "Reconnect" : "Connect"}
          </Button>
        </form>

        <div className={cn("flex-1 py-2", keySlug && "bg-black px-2")}>
          {keySlug ? (
            <ServerTerminal
              key_slug={keySlug}
              key={counter}
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
  key_slug,
  className
}: { key_slug: string; className?: string }) {
  let webSocketScheme = window.location.protocol === "http:" ? "ws" : "wss";
  let apiHost = window.location.host;

  if (apiHost.includes("localhost:5173")) {
    apiHost = "localhost:8000";
  }
  const baseWebSocketURL = `${webSocketScheme}://${apiHost}/ws/server-ssh/${key_slug}`;
  return <Terminal baseWebSocketURL={baseWebSocketURL} className={className} />;
}
