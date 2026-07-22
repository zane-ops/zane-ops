import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  ChevronDownIcon,
  IterationCwIcon,
  LoaderIcon,
  Trash2Icon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { Link, href, useFetcher, useSearchParams } from "react-router";
import type { WorkspaceInvitation } from "~/api/types";
import { Code } from "~/components/code";
import { CopyButton } from "~/components/copy-button";
import { SimpleConfirmationDialog } from "~/components/delete-confirmation-dialog";
import { Pagination } from "~/components/pagination";
import { StatusBadge } from "~/components/status-badge";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "~/components/ui/dialog";
import {
  FieldSet,
  FieldSetLabel,
  FieldSetSelect
} from "~/components/ui/fieldset";
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from "~/components/ui/popover";
import {
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "~/components/ui/select";
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
import { WorkspaceRoleBadge } from "~/components/workspace-role-badge";
import {
  ensureMinRole,
  paginationListFilters,
  workspaceQueries
} from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  cn,
  formattedTime,
  getFormErrorsFromResponseData,
  hasMinRole,
  metaTitle,
  pluralize,
  stringToColor
} from "~/lib/utils";
import {
  getCurrentWorkspace,
  useCurrentWorkspace
} from "~/lib/workspace-store";
import type { clientAction } from "~/routes/settings/workspace-invitation-details";
import type { Route } from "./+types/workspace-invitation-list";

export function meta() {
  return [
    metaTitle("Workspace Invitations")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  await ensureMinRole(queryClient, "Admin");
  const workspace = await getCurrentWorkspace(queryClient);

  const searchParams = new URL(request.url).searchParams;
  const search = paginationListFilters.parse(searchParams);
  const filters = {
    page: search.page ?? 1,
    per_page: search.per_page ?? 10
  };

  const invitations = await queryClient.ensureQueryData(
    workspaceQueries.invitations(workspace.id, filters)
  );
  return {
    invitations
  };
}

export default function WorkspaceInvitationListPage({
  loaderData
}: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const search = paginationListFilters.parse(searchParams);

  const filters = {
    page: search.page ?? 1,
    per_page: search.per_page ?? 10
  };
  const workspaceId = useCurrentWorkspace().id;
  const { data } = useQuery({
    ...workspaceQueries.invitations(workspaceId, filters),
    initialData: loaderData.invitations
  });

  const invitations = data.results;

  const totalPages = Math.ceil(data.count / filters.per_page);
  const emptySearchParams =
    !searchParams.get("per_page") && !searchParams.get("page");

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Pending invitations</h2>
      </div>
      <Separator />
      <div className="flex gap-2 items-center h-9">
        <h3 className="text-grey">Manage your workspace invitations</h3>
        {!emptySearchParams && (
          <Button
            variant="outline"
            className="inline-flex w-min gap-1"
            size="sm"
            asChild
          >
            <Link to="./" prefetch="intent" replace>
              <XIcon size={15} />
              <span>Reset filters</span>
            </Link>
          </Button>
        )}
      </div>

      <WorkspaceInvitationsTable invitations={invitations} />

      <div className="my-4 block">
        {invitations.length > 0 && data.count > 10 && (
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

type WorkspaceInvitationsTableProps = {
  invitations: WorkspaceInvitation[];
};

function WorkspaceInvitationsTable({
  invitations
}: WorkspaceInvitationsTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="sticky top-0 z-20">Username</TableHead>
          <TableHead className="sticky top-0 z-20">Role</TableHead>
          <TableHead className="sticky top-0 z-20">
            Accessible projects
          </TableHead>
          <TableHead className="sticky top-0 z-20">Created at</TableHead>
          <TableHead className="sticky top-0 z-20">Expires at</TableHead>
          <TableHead className="sticky top-0 z-20 px-4">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {invitations.length === 0 ? (
          <TableRow className="px-2">
            <TableCell colSpan={5} className="p-2 text-muted-foreground italic">
              -- No invitations found --
            </TableCell>
          </TableRow>
        ) : (
          invitations.map((invitation) => {
            console.log({
              invitation
            });
            const createdAt = formattedTime(invitation.created_at);
            const expiresAt = formattedTime(invitation.expires_at);
            const isMember = hasMinRole(invitation, "Member");

            return (
              <TableRow className="px-2" key={invitation.id}>
                <TableCell className="p-2">{invitation.username}</TableCell>
                <TableCell className="p-2">
                  <WorkspaceRoleBadge role={invitation.role_name} />
                </TableCell>

                <TableCell className="p-2">
                  {isMember ? (
                    <Code className="px-2 whitespace-nowrap">All projects</Code>
                  ) : (
                    <Popover>
                      <PopoverTrigger asChild>
                        <button className="cursor-pointer">
                          <StatusBadge
                            className="relative top-0.5 text-xs pl-3 pr-2 inline-flex items-center gap-1"
                            color="gray"
                            pingState="hidden"
                          >
                            <span>
                              {invitation.accessible_projects.length}&nbsp;
                              {pluralize(
                                "project",
                                invitation.accessible_projects.length
                              )}
                            </span>

                            <ChevronDownIcon className="flex-none size-4" />
                          </StatusBadge>
                        </button>
                      </PopoverTrigger>
                      <PopoverContent
                        align="start"
                        side="bottom"
                        className="px-4 pt-0 pb-2 w-fit min-w-42"
                      >
                        <ul>
                          <li className="text-xs text-grey my-2">Projects</li>
                          {invitation.accessible_projects.map((project) => {
                            const projectColor = stringToColor(project.slug);
                            return (
                              <li
                                style={
                                  {
                                    "--color-light": projectColor.light,
                                    "--color-dark": projectColor.dark
                                  } as React.CSSProperties
                                }
                                key={project.id}
                                className="inline-flex gap-2 items-center text-sm"
                              >
                                <div
                                  className={cn(
                                    "size-6 flex-none rounded-md flex items-center justify-center",
                                    "text-[var(--color-light)] dark:text-[var(--color-dark)]",
                                    "bg-[var(--color-light)]/10 dark:bg-[var(--color-dark)]/10",
                                    "border  border-[var(--color-light)]/10 dark:border-[var(--color-dark)]/10"
                                  )}
                                >
                                  <span>
                                    {project.slug.charAt(0).toUpperCase()}
                                  </span>
                                </div>
                                <span>{project.slug}</span>
                              </li>
                            );
                          })}
                        </ul>
                      </PopoverContent>
                    </Popover>
                  )}
                </TableCell>
                <TableCell className="p-2">
                  <time
                    className="text-grey whitespace-nowrap"
                    dateTime={new Date(invitation.created_at).toISOString()}
                  >
                    <span>{createdAt}</span>
                  </time>
                </TableCell>
                <TableCell className="p-2">
                  <time
                    className="text-grey whitespace-nowrap"
                    dateTime={new Date(invitation.expires_at).toISOString()}
                  >
                    <span>{expiresAt}</span>
                  </time>
                </TableCell>
                <TableCell className="p-2">
                  <WorkspaceInvitationActions invitation={invitation} />
                </TableCell>
              </TableRow>
            );
          })
        )}
      </TableBody>
    </Table>
  );
}

export type WorkspaceInvitationActionsProps = {
  invitation: WorkspaceInvitation;
};

function getInvitationLink(invitation: Pick<WorkspaceInvitation, "token">) {
  const registerLink =
    window.location.origin +
    href("/invite/:token", { token: invitation.token });
  return registerLink;
}

export function WorkspaceInvitationActions({
  invitation
}: WorkspaceInvitationActionsProps) {
  return (
    <div className="flex items-center gap-1">
      <TooltipProvider>
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <CopyButton
              variant="ghost"
              label="Copy invitation link"
              value={getInvitationLink(invitation)}
              className="!opacity-100 flex-none h-9 rounded-md px-3 text-sm"
            />
          </TooltipTrigger>
          <TooltipContent>Copy invitation link</TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <div className="h-2 relative top-0.5 w-px bg-grey rounded-md" />

      <RegenerateInvitationLinkFormDialog invitation={invitation} />
      <div className="h-2 relative top-0.5 w-px bg-grey rounded-md" />
      <DeleteConfirmationFormDialog invitation={invitation} />
    </div>
  );
}

function RegenerateInvitationLinkFormDialog({
  invitation
}: WorkspaceInvitationActionsProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const validForOptions = Array.from({ length: 7 }, (_, i) => i + 1);

  const fetcher = useFetcher<typeof clientAction>();

  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const [data, setData] = React.useState(fetcher.data);
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(data?.errors);

  const close = React.useCallback(() => {
    setIsOpen(false);
    setData(undefined);
  }, []);

  React.useEffect(() => {
    setData(fetcher.data);
  }, [fetcher.data]);

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (isPending) return;
        setIsOpen(open);
        if (!open) close();
      }}
    >
      <TooltipProvider>
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <DialogTrigger asChild>
              <Button size="sm" variant="ghost" className="gap-1">
                <span className="sr-only">Regenerate link</span>
                <IterationCwIcon className="flex-none size-4" />
              </Button>
            </DialogTrigger>
          </TooltipTrigger>
          <TooltipContent>Regenerate invitation link</TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <DialogContent className="gap-0">
        <DialogHeader>
          <DialogTitle>Regenerate invitation link</DialogTitle>
        </DialogHeader>

        {data?.data ? (
          <div
            className={cn(
              "flex flex-col  my-5 gap-6",
              "border-t border-border -mx-6 px-6 py-4",
              "w-[calc(100%+var(--spacing)*12)]",
              "min-w-0"
            )}
          >
            <p>
              The invitation link has been regenerated. The user must access the
              link below to accept the invitation.
            </p>
            <dl className="flex flex-col gap-2">
              <div className="flex gap-2 items-center">
                <dt className="text-grey">Valid until:</dt>
                <dd>
                  <time dateTime={data.data.expires_at}>
                    {formattedTime(data.data.expires_at)}
                  </time>
                </dd>
              </div>
              <div className="flex items-center gap-2 w-min">
                <dt className="text-grey">New Link:</dt>
                <dd className="flex items-center gap-1.5 grow max-w-65/100">
                  <a
                    href={getInvitationLink(data.data)}
                    target="_blank"
                    className="text-link  hover:underline inline-flex min-w-0 max-w-min items-center  w-full gap-1"
                    rel="noopener"
                  >
                    <p className="whitespace-nowrap text-ellipsis overflow-x-hidden w-full">
                      {getInvitationLink(data.data)}
                    </p>
                  </a>

                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger asChild>
                        <CopyButton
                          value={getInvitationLink(data.data)}
                          label="Copy url"
                          size="icon"
                          className="hover:bg-transparent !opacity-100 size-4 flex-none"
                        />
                      </TooltipTrigger>
                      <TooltipContent>Copy link</TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </dd>
              </div>
            </dl>
          </div>
        ) : (
          <fetcher.Form
            id="confirm-form"
            ref={formRef}
            method="POST"
            action={`./${invitation.id}`}
            className={cn(
              "flex flex-col  my-5 gap-1",
              "border-t border-border -mx-6 px-6 py-4"
            )}
          >
            <p className="mb-4 text-base leading-6.5">
              Are you sure you want to regenerate the invitation link for&nbsp;
              <span className="text-link">{invitation.username}</span>&nbsp;?
              This will revoke the previous link.
            </p>

            {errors.non_field_errors && (
              <Alert variant="destructive">
                <AlertCircleIcon className="h-4 w-4" />
                <AlertTitle>Error</AlertTitle>
                <AlertDescription>{errors.non_field_errors}</AlertDescription>
              </Alert>
            )}
            <input type="hidden" name="intent" value="regenerate-link" />
            <FieldSet
              name="valid_for"
              className="w-full"
              errors={errors.valid_for}
            >
              <FieldSetLabel htmlFor="valid_for">
                New Validity period
              </FieldSetLabel>

              <FieldSetSelect defaultValue={(3).toString()}>
                <SelectTrigger id="valid_for" className="w-full gap-2">
                  <SelectValue placeholder="Select days" />
                </SelectTrigger>
                <SelectContent className="z-999">
                  {validForOptions.map((number) => (
                    <SelectItem value={number.toString()} key={number}>
                      {number} {pluralize("day", number)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </FieldSetSelect>
            </FieldSet>
          </fetcher.Form>
        )}

        <DialogFooter className="-mx-6 px-6">
          <div className={cn("flex items-center gap-4 w-full")}>
            {!data?.data && (
              <SubmitButton
                isPending={isPending}
                form="confirm-form"
                className={cn("inline-flex gap-1 items-center")}
              >
                {isPending ? (
                  <>
                    <LoaderIcon className="animate-spin flex-none" size={15} />
                    <span>Submitting...</span>
                  </>
                ) : (
                  <span>Regenerate</span>
                )}
              </SubmitButton>
            )}

            <DialogClose asChild>
              <Button variant="outline" type="button" disabled={isPending}>
                Close
              </Button>
            </DialogClose>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DeleteConfirmationFormDialog({
  invitation
}: WorkspaceInvitationActionsProps) {
  const fetcher = useFetcher();

  return (
    <SimpleConfirmationDialog
      fetcher={fetcher}
      title="Remove invitation ?"
      variant="warning"
      message={
        <span>
          Once removed, this invitation will no longer be valid. You can always
          re-invite the user later.
        </span>
      }
      form={
        <fetcher.Form method="post" action={`./${invitation.id}`}>
          <input type="hidden" name="intent" value="delete" />
        </fetcher.Form>
      }
      trigger={
        <TooltipProvider>
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <DialogTrigger asChild>
                <Button
                  size="sm"
                  variant="ghost"
                  className="gap-1 text-red-400"
                >
                  <span className="sr-only">Delete invitation</span>
                  <Trash2Icon className="flex-none size-4" />
                </Button>
              </DialogTrigger>
            </TooltipTrigger>
            <TooltipContent>Delete invitation</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      }
    />
  );
}
