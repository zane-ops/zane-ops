import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  CheckIcon,
  ClockAlertIcon,
  LoaderIcon,
  RotateCcwIcon,
  Trash2Icon
} from "lucide-react";
import * as React from "react";
import { href, useFetcher, useSearchParams } from "react-router";

import type { PasswordResetToken } from "~/api/types";
import { CopyButton } from "~/components/copy-button";
import { SimpleConfirmationDialog } from "~/components/delete-confirmation-dialog";
import { Pagination } from "~/components/pagination";
import { StatusBadge } from "~/components/status-badge";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "~/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { passwordTokenListFilters, passwordTokenQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  cn,
  formatLogTime,
  formattedTime,
  getLocalAbsoluteURL,
  metaTitle,
  relativeTimeFormatter
} from "~/lib/utils";
import type { clientAction as userClientAction } from "~/routes/server-admin/server-user-details";
import type { Route } from "./+types/password-link-list";

export function meta() {
  return [
    metaTitle("Password Reset Links")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();

  const searchParams = new URL(request.url).searchParams;
  const search = passwordTokenListFilters.parse(searchParams);
  const filters = {
    page: search.page ?? 1,
    per_page: search.per_page ?? 10,
    ...search
  };

  const tokens = await queryClient.ensureQueryData(
    passwordTokenQueries.list(filters)
  );
  return { tokens };
}

export default function PasswordLinkListPage({
  loaderData
}: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const search = passwordTokenListFilters.parse(searchParams);

  const filters = {
    page: search.page ?? 1,
    per_page: search.per_page ?? 10,
    ...search
  };

  const { data } = useQuery({
    ...passwordTokenQueries.list(filters),
    initialData: loaderData.tokens
  });

  const tokens = data.results;
  const totalPages = Math.ceil(data.count / filters.per_page);

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Password Reset Links</h2>
      </div>
      <Separator />
      <h3 className="text-grey">
        All the password reset links currently issued on this instance
      </h3>

      <Alert variant="warning">
        <AlertCircleIcon className="size-4" />
        <AlertTitle>ZaneOps does not send emails</AlertTitle>
        <AlertDescription>
          Each link is single-use and has to be shared with its owner yourself.
          Delete a link if you are not sure it stayed private.
        </AlertDescription>
      </Alert>

      <PasswordLinkTable tokens={tokens} />

      <div className="my-4 block">
        {tokens.length > 0 && data.count > 10 && (
          <Pagination
            totalPages={totalPages}
            currentPage={filters.page}
            perPage={filters.per_page}
            onChangePage={(newPage) => {
              searchParams.set("page", newPage.toString());
              setSearchParams(searchParams, {
                replace: true
              });
            }}
            onChangePerPage={(newPerPage) => {
              searchParams.set("page", "1");
              searchParams.set("per_page", newPerPage.toString());
              setSearchParams(searchParams, {
                replace: true
              });
            }}
          />
        )}
      </div>
    </section>
  );
}

type PasswordLinkTableProps = {
  tokens: PasswordResetToken[];
};

function PasswordLinkTable({ tokens }: PasswordLinkTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="sticky top-0 z-20">User</TableHead>
          <TableHead className="sticky top-0 z-20 whitespace-nowrap">
            Valid until
          </TableHead>
          <TableHead className="sticky top-0 z-20 px-4 text-end">
            Actions
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {tokens.length === 0 ? (
          <TableRow className="px-2">
            <TableCell colSpan={3} className="p-2 text-muted-foreground italic">
              -- No password reset link has been issued --
            </TableCell>
          </TableRow>
        ) : (
          tokens.map((token) => {
            const expiresAt = formatLogTime(token.expires_at);
            const isExpired = new Date(token.expires_at) <= new Date();

            return (
              <TableRow className="px-2" key={token.id}>
                <TableCell className="p-2">{token.user.username}</TableCell>
                <TableCell className="p-2">
                  <div className="flex items-center gap-1">
                    <time
                      className={cn(
                        "whitespace-nowrap",
                        isExpired ? "text-red-400" : "text-grey"
                      )}
                      dateTime={new Date(token.expires_at).toISOString()}
                    >
                      <span>
                        {expiresAt.dateFormat},&nbsp;
                        <span>{expiresAt.hourFormat}</span>
                      </span>
                    </time>

                    {isExpired && (
                      <StatusBadge
                        color="red"
                        pingState="hidden"
                        className="text-xs py-0.5 px-1.5 gap-1 mx-1 dark:text-red-100"
                      >
                        <span>Expired</span>
                        <ClockAlertIcon className="size-3 flex-none" />
                      </StatusBadge>
                    )}
                  </div>
                </TableCell>

                <TableCell className="p-2 h-14">
                  <div className="flex items-center gap-1 justify-end">
                    <RegenerateLinkFormDialog token={token} />
                    <div className="h-2 relative top-0.5 w-px bg-grey rounded-md" />
                    <DeleteConfirmationFormDialog token={token} />
                  </div>
                </TableCell>
              </TableRow>
            );
          })
        )}
      </TableBody>
    </Table>
  );
}

type RegenerateLinkFormDialogProps = {
  token: PasswordResetToken;
};

function RegenerateLinkFormDialog({ token }: RegenerateLinkFormDialogProps) {
  const fetcher = useFetcher<typeof userClientAction>();
  const [open, setOpen] = React.useState(false);
  const isPending = fetcher.state !== "idle";
  const [data, setData] = React.useState(fetcher.data);

  const newToken = data && "token" in data ? data.token : null;
  const resetLink = newToken
    ? getLocalAbsoluteURL(`/reset-password/${newToken.value}`)
    : null;

  React.useEffect(() => {
    setData(fetcher.data);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetcher.state, fetcher.data]);

  const close = React.useCallback(() => {
    setOpen(false);
    setData(undefined);
  }, []);

  return (
    <Dialog
      open={open}
      onOpenChange={(open) => {
        if (isPending) return;
        setOpen(open);
        if (!open) close();
      }}
    >
      <TooltipProvider>
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <DialogTrigger asChild>
              <Button variant="ghost" size="icon">
                <RotateCcwIcon className="flex-none size-4" />
                <span className="sr-only">
                  Regenerate the password reset link of {token.user.username}
                </span>
              </Button>
            </DialogTrigger>
          </TooltipTrigger>
          <TooltipContent>Regenerate link</TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <DialogContent className="gap-0">
        <DialogHeader className="pb-4">
          <DialogTitle>
            {resetLink ? (
              <>
                New password reset link for&nbsp;
                <span className="text-grey ">
                  &ldquo;{token.user.username}&rdquo;
                </span>
              </>
            ) : (
              <>
                Regenerate the password reset link of&nbsp;
                <span className="text-grey ">
                  &ldquo;{token.user.username}&rdquo;
                </span>
                ?
              </>
            )}
          </DialogTitle>

          {resetLink ? (
            <Alert variant="success" className="mt-5">
              <CheckIcon className="size-4" />
              <AlertTitle>New link ready</AlertTitle>
              <AlertDescription>
                The previous link no longer works. Share this one with{" "}
                <span className="font-medium ">{token.user.username}</span> over
                a channel you trust.
              </AlertDescription>
            </Alert>
          ) : (
            <Alert variant="warning" className="mt-5">
              <AlertCircleIcon className="size-4" />
              <AlertTitle>The current link will stop working</AlertTitle>
              <AlertDescription>
                This replaces the existing link with a new single-use one that
                you will need to share with them yourself. Their current
                password keeps working until they use it.
              </AlertDescription>
            </Alert>
          )}
        </DialogHeader>

        {newToken && resetLink !== null ? (
          <div className="flex flex-col gap-2 mb-5 min-w-0">
            <div
              className={cn(
                "flex items-center gap-2 rounded-md border border-border bg-muted p-2",
                "max-w-full group relative h-14 px-4"
              )}
            >
              <code className="text-sm flex-1 whitespace-nowrap overflow-scroll">
                {resetLink}
              </code>
              <TooltipProvider>
                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <CopyButton
                      variant="outline"
                      size="sm"
                      className="flex-none absolute right-2"
                      value={resetLink}
                      label={(hasCopied?: boolean) =>
                        hasCopied ? "Copied" : "Copy link"
                      }
                    />
                  </TooltipTrigger>
                  <TooltipContent>Copy link</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
            <p className="text-grey text-sm">
              Usable once, until{" "}
              <span className="text-card-foreground">
                {formattedTime(newToken.expires_at)} (
                {relativeTimeFormatter(newToken.expires_at)})
              </span>
              <br /> Generating another link invalidates this one.
            </p>
          </div>
        ) : (
          <fetcher.Form
            method="post"
            action={href("/admin/users/:userId", {
              userId: token.user.id.toString()
            })}
            id="confirm-form"
          >
            <input
              type="hidden"
              name="intent"
              value="generate_password_token"
            />
          </fetcher.Form>
        )}

        <DialogFooter className="-mx-6 px-6">
          <div className="flex items-center gap-4 w-full">
            {resetLink !== null ? (
              <Button variant="outline" type="button" onClick={close}>
                Close
              </Button>
            ) : (
              <>
                <SubmitButton
                  isPending={isPending}
                  variant="warning"
                  form="confirm-form"
                  className={cn("inline-flex gap-1 items-center")}
                >
                  {isPending ? (
                    <>
                      <LoaderIcon
                        className="animate-spin flex-none"
                        size={15}
                      />
                      <span>Regenerating link...</span>
                    </>
                  ) : (
                    <span>Regenerate link</span>
                  )}
                </SubmitButton>

                <Button
                  variant="outline"
                  type="button"
                  disabled={isPending}
                  onClick={() => setOpen(false)}
                >
                  Cancel
                </Button>
              </>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

type DeleteConfirmationFormDialogProps = {
  token: PasswordResetToken;
};

function DeleteConfirmationFormDialog({
  token
}: DeleteConfirmationFormDialogProps) {
  const fetcher = useFetcher();

  return (
    <SimpleConfirmationDialog
      fetcher={fetcher}
      title={
        <>
          Delete the password reset link of&nbsp;
          <span className="text-grey ">
            &ldquo;{token.user.username}&rdquo;
          </span>
          ?
        </>
      }
      message={
        <p>
          The link will stop working immediately, and anyone holding it will no
          longer be able to set their password with it. Their current password
          keeps working.
        </p>
      }
      confirmText="Delete"
      pendingText="Deleting..."
      variant="warning"
      form={
        <fetcher.Form
          method="post"
          action={href("/admin/password-links/:tokenId", {
            tokenId: token.id.toString()
          })}
        >
          <input type="hidden" name="intent" value="delete_password_token" />
        </fetcher.Form>
      }
      trigger={
        <TooltipProvider>
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <DialogTrigger asChild>
                <Button variant="ghost" size="icon">
                  <Trash2Icon className="size-4 flex-none text-red-400" />
                  <span className="sr-only">
                    Delete the password reset link of {token.user.username}
                  </span>
                </Button>
              </DialogTrigger>
            </TooltipTrigger>

            <TooltipContent>Delete link</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      }
    />
  );
}
