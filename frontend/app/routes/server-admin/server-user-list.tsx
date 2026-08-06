import { useQuery } from "@tanstack/react-query";
import {
  BanIcon,
  CrownIcon,
  LoaderIcon,
  PowerIcon,
  PowerOffIcon,
  SearchIcon,
  Trash2Icon,
  UserXIcon,
  XIcon
} from "lucide-react";
import React from "react";
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
import {
  DeleteConfirmationDialog,
  SimpleConfirmationDialog
} from "~/components/delete-confirmation-dialog";
import { Pagination } from "~/components/pagination";
import { StatusBadge } from "~/components/status-badge";
import { Button } from "~/components/ui/button";
import { DialogTrigger } from "~/components/ui/dialog";
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
  getFormErrorsFromResponseData,
  metaTitle
} from "~/lib/utils";
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
        <h2 className="text-2xl">Users in the server</h2>
      </div>
      <Separator />
      <h3 className="text-grey">
        Manage all the users in this ZaneOps instance
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
            className="px-14 -mx-5 w-full my-1 text-sm focus-visible:right-0"
            placeholder="Search users"
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
              -- No users found --
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
                        <span>Disabled</span>
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
                            Server admin
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

                <TableCell className="p-2">
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
      <ToggleUserConfirmationFormDialog user={user} />
      <div className="h-2 relative top-0.5 w-px bg-grey rounded-md" />
      <RemoveConfirmationFormDialog user={user} />
    </div>
  );
}

function ToggleUserConfirmationFormDialog({ user }: ServerUserActionsProps) {
  const fetcher = useFetcher();

  return (
    <SimpleConfirmationDialog
      fetcher={fetcher}
      title={
        <>
          {user.is_active ? "Disable" : "Enable"}&nbsp;
          <span className="text-grey ">&ldquo;{user.username}&rdquo;</span>
          &nbsp;?
        </>
      }
      variant="warning"
      message={
        user.is_active ? (
          <span>
            They will immediately loose any ability to login to this instance,
            until you re-enable them again.
          </span>
        ) : (
          <span>Activate user</span>
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
                    <PowerOffIcon className="flex-none size-4" />
                  ) : (
                    <PowerIcon className="flex-none size-4" />
                  )}
                  <span className="sr-only">
                    {user.is_active ? "Disable User" : "Enable User"}
                  </span>
                </Button>
              </DialogTrigger>
            </TooltipTrigger>
            <TooltipContent>
              {user.is_active ? "Disable User" : "Enable User"}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      }
    />
  );
}

function RemoveConfirmationFormDialog({ user }: ServerUserActionsProps) {
  const fetcher = useFetcher();
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  return (
    <DeleteConfirmationDialog
      title={
        <>
          Delete&nbsp;
          <span className="text-grey ">&ldquo;{user.username}&rdquo;</span>
          &nbsp;from this ZaneOps instance ?
        </>
      }
      fetcher={fetcher}
      message={
        <span>
          They will immediately lose access to this server and all of its
          projects. This action is irreversible.
        </span>
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
                  <span className="sr-only">Delete user</span>
                </Button>
              </DialogTrigger>
            </TooltipTrigger>

            <TooltipContent>Delete user from instance</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      }
    />
  );
}
