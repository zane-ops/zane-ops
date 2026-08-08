import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  BanIcon,
  CheckIcon,
  CrownIcon,
  LoaderIcon,
  LockIcon,
  LockOpenIcon,
  RotateCcwIcon,
  SearchIcon,
  Trash2Icon,
  XIcon
} from "lucide-react";
import * as React from "react";
import {
  Form,
  Link,
  href,
  useFetcher,
  useMatches,
  useSearchParams
} from "react-router";

import { useSpinDelay } from "spin-delay";
import { useDebouncedCallback } from "use-debounce";
import type { User } from "~/api/types";
import { CopyButton } from "~/components/copy-button";
import {
  DeleteConfirmationDialog,
  SimpleConfirmationDialog
} from "~/components/delete-confirmation-dialog";
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
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
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
import { SPIN_DELAY_DEFAULT_OPTIONS } from "~/lib/constants";
import { serverUserListFilters, serverUserQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  cn,
  formatLogTime,
  formattedTime,
  getFormErrorsFromResponseData,
  getLocalAbsoluteURL,
  metaTitle,
  relativeTimeFormatter
} from "~/lib/utils";
import type { clientAction } from "~/routes/server-admin/server-user-details";
import type { Route } from "./+types/server-user-list";

export function meta() {
  return [metaTitle("Server Users")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();

  const searchParams = new URL(request.url).searchParams;
  const search = serverUserListFilters.parse(searchParams);
  const filters = {
    page: search.page ?? 1,
    per_page: search.per_page ?? 10,
    ...search
  };

  const users = await queryClient.ensureQueryData(
    serverUserQueries.list(filters)
  );
  return { users };
}

export default function ServerUserListPage({
  loaderData
}: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const search = serverUserListFilters.parse(searchParams);

  const inputRef = React.useRef<React.ComponentRef<"input">>(null);

  const filters = {
    page: search.page ?? 1,
    per_page: search.per_page ?? 10,
    ...search
  };

  const { data, isFetching } = useQuery({
    ...serverUserQueries.list(filters),
    initialData: loaderData.users
  });

  const isFetchingUsers = useSpinDelay(isFetching, SPIN_DELAY_DEFAULT_OPTIONS);

  const searchUsers = useDebouncedCallback((query: string) => {
    searchParams.set("query", query);
    setSearchParams(searchParams, { replace: true });
  }, 300);

  React.useEffect(() => {
    if (inputRef.current && inputRef.current.value !== filters.query) {
      inputRef.current.value = filters.query ?? "";
    }
  }, [filters.query]);

  const users = data.results;

  const totalPages = Math.ceil(data.count / filters.per_page);
  const emptySearchParams =
    !(searchParams.get("query")?.trim() ?? "") &&
    !searchParams.get("per_page") &&
    !searchParams.get("page");

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Users</h2>
      </div>
      <Separator />
      <h3 className="text-grey">
        Manage everyone who has access to this ZaneOps instance
      </h3>

      <Form className="flex flex-wrap items-center md:gap-3 gap-1">
        <FieldSet name="query" className="flex md:w-[30%] w-full items-center">
          <FieldSetLabel className="sr-only">Search query</FieldSetLabel>

          {isFetchingUsers ? (
            <LoaderIcon size={20} className="animate-spin relative left-4" />
          ) : (
            <SearchIcon size={20} className="relative left-4" />
          )}

          <FieldSetInput
            onChange={(e) => {
              searchUsers(e.currentTarget.value);
            }}
            ref={inputRef}
            defaultValue={filters.query}
            className="pl-14 -mx-5 w-full my-1 text-sm focus-visible:right-0"
            placeholder="Search by name"
          />
        </FieldSet>

        {!emptySearchParams && (
          <Button variant="outline" className="inline-flex w-min gap-1" asChild>
            <Link to="./" prefetch="intent" replace>
              <XIcon size={15} />
              <span>Reset filters</span>
            </Link>
          </Button>
        )}
      </Form>

      <InstanceUserTable users={users} />

      <div className="my-4 block">
        {users.length > 0 && data.count > 10 && (
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

type InstanceUserTableProps = {
  users: User[];
};

function InstanceUserTable({ users }: InstanceUserTableProps) {
  const {
    "1": {
      loaderData: {
        user: { user: currentUser }
      }
    }
  } = useMatches() as Route.ComponentProps["matches"];

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="sticky top-0 z-20">Username</TableHead>
          <TableHead className="sticky top-0 z-20 whitespace-nowrap">
            Display Name
          </TableHead>
          <TableHead className="sticky top-0 z-20">Joined at</TableHead>
          <TableHead className="sticky top-0 z-20 px-4">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {users.length === 0 ? (
          <TableRow className="px-2">
            <TableCell colSpan={5} className="p-2 text-muted-foreground italic">
              -- No users match your search --
            </TableCell>
          </TableRow>
        ) : (
          users.map((user) => {
            const joinedAt = formatLogTime(user.date_joined);
            const isSelf = currentUser?.username === user.username;
            const showActions = !isSelf && !user.is_superuser;

            return (
              <TableRow className="px-2" key={user.id}>
                <TableCell className="p-2">
                  <div className="flex items-center gap-1 justify-star">
                    <span>
                      {user.username}
                      {isSelf && (
                        <>
                          &nbsp;
                          <span>&middot;</span>&nbsp;
                          <span className="text-link text-sm">you</span>
                        </>
                      )}
                    </span>

                    {!user.is_active && (
                      <StatusBadge
                        color="red"
                        pingState="hidden"
                        className="text-xs py-0.5 px-1.5 gap-1 mx-1 dark:text-red-100"
                      >
                        <span>Blocked</span>
                        <BanIcon className="size-3 flex-none" />
                      </StatusBadge>
                    )}

                    {user.is_superuser && (
                      <TooltipProvider>
                        <Tooltip delayDuration={0}>
                          <TooltipTrigger asChild>
                            <span
                              className={cn(
                                "inline-flex cursor-help",
                                isSelf ? "text-link" : "text-grey"
                              )}
                            >
                              <CrownIcon className="size-4 flex-none" />
                            </span>
                          </TooltipTrigger>
                          <TooltipContent
                            side="top"
                            className="max-w-60 text-pretty"
                          >
                            <strong className="font-medium underline">
                              Server admin
                            </strong>
                            , has full access to this instance and cannot be
                            blocked or deleted
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    )}
                  </div>
                </TableCell>
                <TableCell className="p-2 whitespace-nowrap">
                  {user.first_name || (
                    <span className="text-grey font-mono">N/A</span>
                  )}
                </TableCell>
                <TableCell className="p-2">
                  <time
                    className="text-grey whitespace-nowrap"
                    dateTime={new Date(user.date_joined).toISOString()}
                  >
                    <span>
                      {joinedAt.dateFormat},&nbsp;
                      <span>{joinedAt.hourFormat}</span>
                    </span>
                  </time>
                </TableCell>

                <TableCell className={cn("p-2 h-14")}>
                  {showActions && <ServerUserActions user={user} />}
                </TableCell>
              </TableRow>
            );
          })
        )}
      </TableBody>
    </Table>
  );
}

type ServerUserActionsProps = {
  user: User;
};

export function ServerUserActions({ user }: ServerUserActionsProps) {
  return (
    <div className="flex items-center gap-1">
      <PasswordTokenGenerateFormDialog user={user} />
      <div className="h-2 relative top-0.5 w-px bg-grey rounded-md" />
      <ToggleUserConfirmationFormDialog user={user} />
      <div className="h-2 relative top-0.5 w-px bg-grey rounded-md" />
      <RemoveConfirmationFormDialog user={user} />
    </div>
  );
}

export type PasswordTokenGenerateFormDialogProps = {
  user: User;
};

export function PasswordTokenGenerateFormDialog({
  user
}: PasswordTokenGenerateFormDialogProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const [open, setOpen] = React.useState(false);
  const isPending = fetcher.state !== "idle";
  const [data, setData] = React.useState(fetcher.data);

  const token = data && "token" in data ? data.token : null;
  const resetLink = token
    ? getLocalAbsoluteURL(`/reset-password/${token.value}`)
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
                  Create a password reset link for {user.username}
                </span>
              </Button>
            </DialogTrigger>
          </TooltipTrigger>
          <TooltipContent>Reset password</TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <DialogContent className="gap-0">
        <DialogHeader className="pb-4">
          <DialogTitle>
            {resetLink ? (
              <>
                Password Reset link for&nbsp;
                <span className="text-grey ">
                  &ldquo;{user.username}&rdquo;
                </span>
              </>
            ) : (
              <>
                Reset the password of&nbsp;
                <span className="text-grey ">
                  &ldquo;{user.username}&rdquo;
                </span>
                ?
              </>
            )}
          </DialogTitle>

          {resetLink ? (
            <Alert variant="success" className="mt-5">
              <CheckIcon className="size-4" />
              <AlertTitle>Link ready</AlertTitle>
              <AlertDescription>
                Share it with{" "}
                <span className="font-medium ">{user.username}</span> over a
                channel you trust. Anyone holding this link can set their
                password.
              </AlertDescription>
            </Alert>
          ) : (
            <Alert variant="warning" className="mt-5">
              <AlertCircleIcon className="size-4" />
              <AlertTitle>ZaneOps does not send emails</AlertTitle>
              <AlertDescription>
                This creates a single-use link that you will need to share with
                them yourself. Their current password keeps working until they
                use it.
              </AlertDescription>
            </Alert>
          )}
        </DialogHeader>

        {token && resetLink !== null ? (
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
                {formattedTime(token.expires_at)} (
                {relativeTimeFormatter(token.expires_at)})
              </span>
              <br /> Generating another link invalidates this one.
            </p>
          </div>
        ) : (
          <fetcher.Form
            method="post"
            action={href("/admin/users/:userId", {
              userId: user.id.toString()
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
                      <span>Generating link...</span>
                    </>
                  ) : (
                    <span>Generate reset link</span>
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

function ToggleUserConfirmationFormDialog({ user }: ServerUserActionsProps) {
  const fetcher = useFetcher();

  return (
    <SimpleConfirmationDialog
      fetcher={fetcher}
      title={
        <>
          {user.is_active ? "Block" : "Unblock"}&nbsp;
          <span className="text-grey ">&ldquo;{user.username}&rdquo;</span>?
        </>
      }
      variant="warning"
      message={
        user.is_active ? (
          <span>
            They won&apos;t be able to log in to this instance until you unblock
            them. Their projects and services will keep running.
          </span>
        ) : (
          <span>
            They will be able to log back in to this instance and regain access
            to their projects and services.
          </span>
        )
      }
      form={
        <fetcher.Form
          method="post"
          action={href("/admin/users/:userId", {
            userId: user.id.toString()
          })}
        >
          <input
            type="hidden"
            name="is_active"
            value={user.is_active ? "off" : "on"}
          />
          <input type="hidden" name="intent" value="toggle_user_active" />
        </fetcher.Form>
      }
      trigger={
        <TooltipProvider>
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <DialogTrigger asChild>
                <Button variant="ghost" size="icon">
                  {user.is_active ? (
                    <LockIcon className="flex-none size-4" />
                  ) : (
                    <LockOpenIcon className="flex-none size-4" />
                  )}
                  <span className="sr-only">
                    {user.is_active
                      ? `Block ${user.username}`
                      : `Unblock ${user.username}`}
                  </span>
                </Button>
              </DialogTrigger>
            </TooltipTrigger>
            <TooltipContent>
              {user.is_active ? "Block user" : "Unblock user"}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      }
    />
  );
}

function RemoveConfirmationFormDialog({ user }: ServerUserActionsProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  return (
    <DeleteConfirmationDialog
      title={
        <>
          Delete&nbsp;
          <span className="text-grey ">&ldquo;{user.username}&rdquo;</span>
          &nbsp;from this ZaneOps instance?
        </>
      }
      fetcher={fetcher}
      message={
        <p>
          They will immediately lose access to this instance and everything in
          it. Projects and services they created will keep running, but nobody
          will be able to log in as them again. <br />
          <strong>This action cannot be undone.</strong>
        </p>
      }
      confirmationValue={user.username}
      confirmationFieldName="username"
      form={
        <fetcher.Form
          method="post"
          action={href("/admin/users/:userId", {
            userId: user.id.toString()
          })}
        >
          <FieldSet name="username" errors={errors.username}>
            <FieldSetInput />
          </FieldSet>
          <input type="hidden" name="intent" value="delete_user" />
        </fetcher.Form>
      }
      trigger={
        <TooltipProvider>
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <DialogTrigger asChild>
                <Button variant="ghost" size="icon">
                  <Trash2Icon className="size-4 flex-none text-red-400" />
                  <span className="sr-only">Delete {user.username}</span>
                </Button>
              </DialogTrigger>
            </TooltipTrigger>

            <TooltipContent>Delete user</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      }
    />
  );
}
