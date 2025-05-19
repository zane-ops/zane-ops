import { useQuery } from "@tanstack/react-query";
import {
  ClockIcon,
  FingerprintIcon,
  KeyRoundIcon,
  PlusIcon,
  Trash2Icon,
  UserIcon
} from "lucide-react";
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
import type { Route } from "./+types/ssh-keys-list";

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
      <p>This is a list of SSH keys used to connect to your servers.</p>

      <ul className="flex flex-col gap-2">
        {sshKeys.length === 0 ? (
          <div className="border-border border-dashed border-1 flex items-center justify-center p-6 text-grey">
            No SSH Key found
          </div>
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
        <div className="flex flex-col gap-2 items-center text-grey">
          <KeyRoundIcon size={30} className="flex-none" />
          <Badge variant="outline" className="text-grey">
            SSH
          </Badge>
        </div>
        <div className="flex flex-col flex-1 gap-0.5">
          <h3 className="font-medium text-lg">{ssh_key.slug}</h3>
          <div className="text-link flex items-center gap-1">
            <UserIcon size={15} /> <span>{ssh_key.user}</span>
          </div>
          <div className="text-sm text-grey flex items-center gap-1">
            <FingerprintIcon size={15} />
            <span>{ssh_key.fingerprint}</span>
          </div>
          <div className="text-grey text-sm flex items-center gap-1">
            <ClockIcon size={15} />
            <span>
              Added on&nbsp;
              <time dateTime={ssh_key.created_at}>
                {formattedDate(ssh_key.created_at)}
              </time>
            </span>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <TooltipProvider>
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <CopyButton
                  value={ssh_key.public_key}
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
