import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  ClockIcon,
  FingerprintIcon,
  KeyRoundIcon,
  LoaderIcon,
  PlusIcon,
  TerminalIcon,
  Trash2Icon,
  UserIcon
} from "lucide-react";
import * as React from "react";
import { Link, href, redirect, useFetcher } from "react-router";
import { apiClient } from "~/api/client";
import { CopyButton } from "~/components/copy-button";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Badge } from "~/components/ui/badge";
import { Button, SubmitButton } from "~/components/ui/button";
import { Card, CardContent } from "~/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "~/components/ui/dialog";
import { Separator } from "~/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { type SSHKey, sshKeysQueries } from "~/lib/queries";
import { cn } from "~/lib/utils";
import { queryClient } from "~/root";
import { formattedDate, getCsrfTokenHeader, metaTitle } from "~/utils";
import type { Route } from "./+types/ssh-keys-list";

export function meta() {
  return [metaTitle("SSH Keys")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader() {
  const sshKeys = await queryClient.ensureQueryData(sshKeysQueries.list);
  return { sshKeys };
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const formData = await request.formData();

  const { error: errors } = await apiClient.DELETE(
    "/api/shell/ssh-keys/{slug}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          slug: formData.get("slug")?.toString() ?? "<invalid>"
        }
      }
    }
  );

  if (errors) {
    return {
      errors
    };
  }

  await queryClient.invalidateQueries(sshKeysQueries.list);
  throw redirect(href("/settings/ssh-keys"));
}

export default function SSHKeysPagePage({ loaderData }: Route.ComponentProps) {
  const { data: sshKeys } = useQuery({
    ...sshKeysQueries.list,
    initialData: loaderData.sshKeys
  });

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">SSH keys</h2>
        <Button asChild variant="secondary" className="flex gap-2">
          <Link to="new" prefetch="intent">
            New Key <PlusIcon size={18} />
          </Link>
        </Button>
      </div>
      <Separator />
      <h3 className="text-grey">
        This is a list of SSH keys used to connect to your servers.
      </h3>

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
    </section>
  );
}

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
                      pathname: href("/settings/server-console"),
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
          <DeleteConfirmationFormDialog key_slug={ssh_key.slug} />
        </div>
      </CardContent>
    </Card>
  );
}

function DeleteConfirmationFormDialog({ key_slug }: { key_slug: string }) {
  const [isOpen, setIsOpen] = React.useState(false);
  const fetcher = useFetcher<typeof clientAction>();

  const isPending = fetcher.state !== "idle";

  React.useEffect(() => {
    // only focus on the correct input in case of error
    if (fetcher.state === "idle" && fetcher.data && !fetcher.data.errors) {
      setIsOpen(false);
    }
  }, [fetcher.state, fetcher.data]);

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <TooltipProvider>
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <DialogTrigger asChild>
              <Button size="sm" variant="ghost">
                <Trash2Icon className="text-red-400" size={15} />
                <span className="sr-only">Delete SSH key</span>
              </Button>
            </DialogTrigger>
          </TooltipTrigger>
          <TooltipContent>Delete Key</TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <DialogContent className="gap-0">
        <DialogHeader>
          <DialogTitle>Delete this SSH Key ?</DialogTitle>

          <Alert variant="destructive" className="my-5">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Warning</AlertTitle>
            <AlertDescription>
              This action <strong>CANNOT</strong> be undone. This will
              permanently delete the SSH key.
            </AlertDescription>
          </Alert>
        </DialogHeader>

        <DialogFooter className="-mx-6 px-6">
          <fetcher.Form
            method="post"
            className="flex items-center gap-4 w-full"
          >
            <input type="hidden" name="slug" value={key_slug} />

            <SubmitButton
              isPending={isPending}
              variant="destructive"
              className={cn(
                "inline-flex gap-1 items-center",
                isPending ? "bg-red-400" : "bg-red-500"
              )}
            >
              {isPending ? (
                <>
                  <LoaderIcon className="animate-spin flex-none" size={15} />
                  <span>Submitting...</span>
                </>
              ) : (
                <>
                  <span>Confirm</span>
                </>
              )}
            </SubmitButton>

            <Button
              variant="outline"
              type="button"
              onClick={() => setIsOpen(false)}
            >
              Cancel
            </Button>
          </fetcher.Form>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
