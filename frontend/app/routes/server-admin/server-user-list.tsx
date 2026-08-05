import { useQuery } from "@tanstack/react-query";
import { CrownIcon, LoaderIcon, SearchIcon, XIcon } from "lucide-react";
import React from "react";
import {
  Form,
  Link,
  useFetcher,
  useMatches,
  useSearchParams
} from "react-router";

import { useSpinDelay } from "spin-delay";
import { useDebouncedCallback } from "use-debounce";
import type { User } from "~/api/types";
import { Pagination } from "~/components/pagination";
import { Button } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
import { Separator } from "~/components/ui/separator";
import { Switch } from "~/components/ui/switch";
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
import { cn, formatLogTime, metaTitle } from "~/lib/utils";
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
        user: { user }
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
          <TableHead className="sticky top-0 z-20">Active</TableHead>
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
          users.map((u) => {
            const joinedAt = formatLogTime(u.date_joined);

            const isSelf = user?.username === u.username;

            const showActions = !isSelf;

            return (
              <TableRow className="px-2" key={u.id}>
                <TableCell className="p-2">
                  <div className="flex items-center gap-1 justify-start">
                    <span>
                      {u.username}
                      {isSelf && (
                        <>
                          &nbsp;
                          <span>&middot;</span>&nbsp;
                          <span className="text-link text-sm">you</span>
                        </>
                      )}
                    </span>

                    {u.is_superuser && (
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
                  {u.first_name || (
                    <span className="text-grey font-mono">N/A</span>
                  )}
                </TableCell>
                <TableCell className="p-2">
                  <time
                    className="text-grey whitespace-nowrap"
                    dateTime={new Date(u.date_joined).toISOString()}
                  >
                    <span>
                      {joinedAt.dateFormat},&nbsp;
                      <span>{joinedAt.hourFormat}</span>
                    </span>
                  </time>
                </TableCell>
                <TableCell className="p-2 py-3">
                  <ToggleUserStateForm user={u} />
                </TableCell>
                <TableCell className="p-2"></TableCell>

                <TableCell className="p-2">
                  {/* {showActions && <WorkspaceMemberActions member={u} />} */}
                </TableCell>
              </TableRow>
            );
          })
        )}
      </TableBody>
    </Table>
  );
}

type ToggleUserStateFormProps = {
  user: User;
};
function ToggleUserStateForm({ user }: ToggleUserStateFormProps) {
  const fetcher = useFetcher();

  return (
    <fetcher.Form action={`./${user.id}`} method="POST">
      <Switch defaultChecked={user.is_active} />
    </fetcher.Form>
  );
}
