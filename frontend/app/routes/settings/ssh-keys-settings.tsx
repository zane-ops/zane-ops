import { useQuery } from "@tanstack/react-query";
import { KeyRoundIcon, PlusIcon, Trash2Icon } from "lucide-react";
import { Link } from "react-router";
import { CopyButton } from "~/components/copy-button";
import { Badge } from "~/components/ui/badge";
import { Button } from "~/components/ui/button";
import { Card, CardContent } from "~/components/ui/card";
import { Separator } from "~/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { sshKeysQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { formattedDate } from "~/utils";
import type { Route } from "./+types/ssh-keys-settings";

export async function clientLoader() {
  const sshKeys = await queryClient.ensureQueryData(sshKeysQueries.list);
  return { sshKeys };
}

export default function SSHKeysPagePage({ loaderData }: Route.ComponentProps) {
  const { data: sshKeys } = useQuery({
    ...sshKeysQueries.list,
    initialData: loaderData.sshKeys
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">SSH keys</h2>
        <Button asChild variant="secondary" className="flex gap-2">
          <Link to="new" prefetch="intent">
            New Key <PlusIcon size={18} />
          </Link>
        </Button>
      </div>
      <Separator />
      <p className="text-sm">
        This is a list of SSH keys associated with your account. Remove any keys
        that you do not recognize.
      </p>

      <ul className="flex flex-col gap-2">
        {sshKeys.length === 0 ? (
          <></>
        ) : (
          sshKeys.map((ssh_key) => (
            <li key={ssh_key.id}>
              <SSHKeyCard ssh_key={ssh_key} />
            </li>
          ))
        )}
      </ul>
    </div>
  );
}

export type SSHKeyCardProps = {
  ssh_key: Route.ComponentProps["loaderData"]["sshKeys"][number];
};

export function SSHKeyCard({ ssh_key }: SSHKeyCardProps) {
  return (
    <Card>
      <CardContent className="rounded-md p-4 gap-4 flex items-center bg-toggle">
        <div className="flex flex-col gap-2 items-center">
          <KeyRoundIcon size={30} className="text-grey flex-none" />
          <Badge variant="outline">SSH</Badge>
        </div>
        <div className="flex flex-col flex-1">
          <h3>{ssh_key.slug}</h3>
          <p className="text-grey">
            Added on&nbsp;
            <time dateTime={ssh_key.created_at}>
              {formattedDate(ssh_key.created_at)}
            </time>
          </p>
        </div>
        <div className="flex items-center gap-1">
          <TooltipProvider>
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <CopyButton
                  value="hello"
                  label="Copy Public Key"
                  className="!opacity-100"
                />
              </TooltipTrigger>
              <TooltipContent>Copy Public Key</TooltipContent>
            </Tooltip>
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <Button size="sm" variant="ghost">
                  <Trash2Icon className="text-red-400" size={15} />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Delete Key</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </CardContent>
    </Card>
  );
}
