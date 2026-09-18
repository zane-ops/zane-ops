import {
  ClockIcon,
  FingerprintIcon,
  KeyRoundIcon,
  TerminalIcon,
  Trash2Icon,
  UserIcon
} from "lucide-react";

import { Link, href, useFetcher } from "react-router";
import type { SSHKey } from "~/api/types";
import { Code } from "~/components/code";
import { CopyButton } from "~/components/copy-button";
import { SimpleConfirmationDialog } from "~/components/delete-confirmation-dialog";
import { Badge } from "~/components/ui/badge";
import { Button } from "~/components/ui/button";
import { Card, CardContent } from "~/components/ui/card";
import { DialogTrigger } from "~/components/ui/dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { cn, formattedDate } from "~/lib/utils";

type SSHKeyCardProps = {
  sshKey: SSHKey;
  serverId: string;
  className?: string;
};

export function SSHKeyCard({ sshKey, className, serverId }: SSHKeyCardProps) {
  return (
    <Card>
      <CardContent
        className={cn(
          "rounded-md p-4 pl-5 pt-3 gap-3 flex flex-col items-start bg-toggle",
          "md:flex-row md:items-center",
          "relative",
          className
        )}
      >
        <div className="flex-col gap-2 items-center text-grey hidden md:flex">
          <KeyRoundIcon className="flex-none size-5.5" />
          <Badge variant="outline" className="text-grey text-xs">
            ssh
          </Badge>
        </div>
        <div className="flex flex-col flex-1 gap-0.5 pr-3 text-sm">
          <h3 className="font-medium text-base">{sshKey.slug}</h3>
          <div className="text-link flex items-center gap-1">
            <UserIcon size={15} className="flex-none" />
            <span>{sshKey.user}</span>
          </div>
          <div className="text-sm text-grey flex items-center gap-1">
            <FingerprintIcon size={15} className="flex-none" />
            <span className="break-all">
              {sshKey.fingerprint?.toLowerCase()}
            </span>
          </div>
          <div className="text-grey text-sm flex items-center gap-1">
            <ClockIcon size={15} className="flex-none" />
            <span>
              Added on&nbsp;
              <time dateTime={sshKey.created_at}>
                {formattedDate(sshKey.created_at)}
              </time>
            </span>
          </div>
        </div>

        <div className="absolute top-2 right-2 flex items-center gap-1">
          <TooltipProvider>
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <Button size="sm" variant="ghost" asChild>
                  <Link
                    to={{
                      pathname: href("/admin/servers/:serverId/console", {
                        serverId
                      }),
                      search: `?ssh_key_slug=${encodeURIComponent(sshKey.slug)}`
                    }}
                  >
                    <TerminalIcon size={15} />
                    <span className="sr-only">
                      Use this Key to connect to the server's console
                    </span>
                  </Link>
                </Button>
              </TooltipTrigger>
              <TooltipContent className="max-w-60 text-pretty">
                Open console with this key
              </TooltipContent>
            </Tooltip>
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <CopyButton
                  value={sshKey.public_key}
                  label="Copy Public Key"
                  className="!opacity-100"
                />
              </TooltipTrigger>
              <TooltipContent>Copy Public Key</TooltipContent>
            </Tooltip>
          </TooltipProvider>
          <DeleteConfirmationFormDialog sshKey={sshKey} />
        </div>
      </CardContent>
    </Card>
  );
}

type DeleteConfirmationFormDialogProps = {
  sshKey: SSHKey;
};

function DeleteConfirmationFormDialog({
  sshKey
}: DeleteConfirmationFormDialogProps) {
  const fetcher = useFetcher();

  return (
    <SimpleConfirmationDialog
      fetcher={fetcher}
      title={
        <>
          Delete the SSH key&nbsp;
          <span className="text-grey">&ldquo;{sshKey.slug}&rdquo;</span>?
        </>
      }
      message={
        <p>
          You will no longer be able to open a console on this server with this
          key. Remember to also remove the public key from the{" "}
          <Code>~/.ssh/authorized_keys</Code> file on the server.
        </p>
      }
      confirmText="Delete"
      pendingText="Deleting..."
      form={
        <fetcher.Form
          method="post"
          action={href("/admin/ssh-keys/:slug", { slug: sshKey.slug })}
        >
          <input type="hidden" name="intent" value="delete_ssh_key" />
        </fetcher.Form>
      }
      trigger={
        <TooltipProvider>
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <DialogTrigger asChild>
                <Button size="sm" variant="ghost">
                  <Trash2Icon size={15} className="text-red-400" />
                  <span className="sr-only">Delete SSH key {sshKey.slug}</span>
                </Button>
              </DialogTrigger>
            </TooltipTrigger>
            <TooltipContent>Delete SSH key</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      }
    />
  );
}
