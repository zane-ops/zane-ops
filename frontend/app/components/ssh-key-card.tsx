import {
  ClockIcon,
  FingerprintIcon,
  KeyRoundIcon,
  TerminalIcon,
  UserIcon
} from "lucide-react";

import { Link, href } from "react-router";
import type { SSHKey } from "~/api/types";
import { CopyButton } from "~/components/copy-button";
import { Badge } from "~/components/ui/badge";
import { Button } from "~/components/ui/button";
import { Card, CardContent } from "~/components/ui/card";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { formattedDate } from "~/lib/utils";

type SSHKeyCardProps = {
  ssh_key: SSHKey;
};

function SSHKeyCard({ ssh_key }: SSHKeyCardProps) {
  return (
    <Card>
      <CardContent className="rounded-md p-4 gap-4 flex flex-col items-start md:flex-row md:items-center bg-toggle">
        <div className=" flex-col gap-2 items-center text-grey hidden md:flex">
          <KeyRoundIcon size={30} className="flex-none" />
          <Badge variant="outline" className="text-grey">
            SSH
          </Badge>
        </div>
        <div className="flex flex-col flex-1 gap-0.5">
          <h3 className="font-medium text-lg">{ssh_key.slug}</h3>
          <div className="text-link flex items-center gap-1">
            <UserIcon size={15} className="flex-none" />
            <span>{ssh_key.user}</span>
          </div>
          <div className="text-sm text-grey flex items-center gap-1">
            <FingerprintIcon size={15} className="flex-none" />
            <span className="break-all">{ssh_key.fingerprint}</span>
          </div>
          <div className="text-grey text-sm flex items-center gap-1">
            <ClockIcon size={15} className="flex-none" />
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
                <Button size="sm" variant="ghost" asChild>
                  <Link
                    to={{
                      pathname: href("/admin/server-console"),
                      search: `?ssh_key_slug=${encodeURIComponent(ssh_key.slug)}`
                    }}
                  >
                    <TerminalIcon size={15} />
                    <span className="sr-only">
                      login via SSH using this key
                    </span>
                  </Link>
                </Button>
              </TooltipTrigger>
              <TooltipContent>login via SSH using this key</TooltipContent>
            </Tooltip>
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
          </TooltipProvider>
          {/* <DeleteConfirmationFormDialog key_slug={ssh_key.slug} /> */}
        </div>
      </CardContent>
    </Card>
  );
}
