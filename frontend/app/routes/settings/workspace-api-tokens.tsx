import { useQuery } from "@tanstack/react-query";
import {
  BadgeCheckIcon,
  BanIcon,
  ChevronDownIcon,
  CircleCheckIcon,
  ClockAlertIcon,
  ClockFadingIcon,
  type LucideIcon,
  PlusIcon,
  Trash2Icon
} from "lucide-react";
import type * as React from "react";
import { Link, useFetcher, useSearchParams } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import type { WorkspaceApiToken, WorkspaceRoleName } from "~/api/types";
import { Code } from "~/components/code";
import { SimpleConfirmationDialog } from "~/components/delete-confirmation-dialog";
import { StatusBadge, type StatusBadgeColor } from "~/components/status-badge";
import { Button } from "~/components/ui/button";
import { DialogTrigger } from "~/components/ui/dialog";
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from "~/components/ui/popover";
import {
  Select,
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
import { WORKSPACE_ROLE_MAPPING } from "~/lib/constants";
import { apiTokenQueries, ensureMinRole } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  cn,
  formatLogTime,
  getCsrfTokenHeader,
  metaTitle,
  pluralize,
  stringToColor
} from "~/lib/utils";
import {
  getCurrentWorkspace,
  useCurrentWorkspace
} from "~/lib/workspace-store";
import type { Route } from "./+types/workspace-api-tokens";

export function meta() {
  return [metaTitle("API Tokens")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  await ensureMinRole(queryClient, "Member");

  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  const searchParams = new URL(request.url).searchParams;
  const revoked = searchParams.get("revoked") === "true";

  const tokens = await queryClient.ensureQueryData(
    apiTokenQueries.list(workspaceId, { revoked })
  );
  return { tokens };
}

export default function WorkspaceAPITokensPage({
  loaderData
}: Route.ComponentProps) {
  const workspaceId = useCurrentWorkspace().id;
  const [searchParams, setSearchParams] = useSearchParams();
  const showRevoked = searchParams.get("revoked") === "true";

  const { data: tokens } = useQuery({
    ...apiTokenQueries.list(workspaceId, { revoked: showRevoked }),
    initialData: loaderData.tokens
  });

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">API Tokens</h2>
        <Button asChild variant="secondary" className="flex gap-2">
          <Link to="new" prefetch="intent">
            New <PlusIcon size={18} />
          </Link>
        </Button>
      </div>
      <Separator />
      <div className="flex flex-col items-start gap-4">
        <h3 className="text-grey">
          Tokens let scripts and CI pipelines call the ZaneOps API without a
          browser session.
        </h3>

        <Select
          value={showRevoked ? "all" : "active"}
          onValueChange={(value) => {
            if (value === "all") {
              searchParams.set("revoked", "true");
            } else {
              searchParams.delete("revoked");
            }
            setSearchParams(searchParams, { replace: true });
          }}
        >
          <SelectTrigger className="w-36 flex-none">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="active">Active</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="sticky top-0 z-20">Name</TableHead>
            <TableHead className="sticky top-0 z-20">Token</TableHead>
            <TableHead className="sticky top-0 z-20">Role</TableHead>
            <TableHead className="sticky top-0 z-20">Scopes</TableHead>
            <TableHead className="sticky top-0 z-20">Projects</TableHead>
            <TableHead className="sticky top-0 z-20">Status</TableHead>
            <TableHead className="sticky top-0 z-20">Created At</TableHead>
            <TableHead className="sticky top-0 z-20">Expires</TableHead>
            <TableHead className="sticky top-0 z-20">Created by</TableHead>
            <TableHead className="sticky top-0 z-20 px-4">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {tokens.length === 0 ? (
            <TableRow className="px-2">
              <TableCell
                colSpan={9}
                className="p-2 text-muted-foreground italic"
              >
                -- No API tokens found --
              </TableCell>
            </TableRow>
          ) : (
            tokens.map((token) => <TokenRow key={token.id} token={token} />)
          )}
        </TableBody>
      </Table>
    </section>
  );
}

function getTokenStatus(token: WorkspaceApiToken): {
  label: string;
  color: StatusBadgeColor;
  Icon: LucideIcon;
} {
  if (token.revoked_at)
    return { label: "Revoked", color: "red", Icon: BanIcon };
  if (!token.is_active)
    return { label: "Expired", color: "yellow", Icon: ClockFadingIcon };
  return { label: "Active", color: "green", Icon: BadgeCheckIcon };
}

function TokenRow({ token }: { token: WorkspaceApiToken }) {
  const status = getTokenStatus(token);
  const roleName = token.role_name as WorkspaceRoleName;
  const expiresAt = formatLogTime(token.expires_at);
  const createdAt = formatLogTime(token.created_at);

  return (
    <TableRow className="px-2">
      <TableCell className="p-2">{token.name}</TableCell>
      <TableCell className="p-2">
        <Code>{token.masked_token}</Code>
      </TableCell>
      <TableCell className="p-2">
        <TooltipProvider>
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <span className="inline-flex cursor-help">
                <WorkspaceRoleBadge role={roleName} />
              </span>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-60 text-pretty">
              {WORKSPACE_ROLE_MAPPING[roleName]?.description}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </TableCell>
      <TableCell className="p-2">
        {token.scopes.length === 0 ? (
          <span className="text-grey font-mono text-sm">N/A</span>
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
                    {token.scopes.length}&nbsp;
                    {pluralize("scope", token.scopes.length)}
                  </span>
                  <ChevronDownIcon className="flex-none size-4" />
                </StatusBadge>
              </button>
            </PopoverTrigger>
            <PopoverContent
              align="start"
              side="bottom"
              className="px-4 pt-0 pb-3 w-fit min-w-48"
            >
              <ul className="flex flex-col gap-1">
                <li className="text-xs text-grey my-2">Scopes</li>
                {token.scopes.map((scope) => (
                  <li key={scope} className="text-sm py-0.5">
                    <Code>{scope}</Code>
                  </li>
                ))}
              </ul>
            </PopoverContent>
          </Popover>
        )}
      </TableCell>
      <TableCell className="p-2">
        {token.accessible_projects.length === 0 ? (
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
                    {token.accessible_projects.length}&nbsp;
                    {pluralize("project", token.accessible_projects.length)}
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
                {token.accessible_projects.map((project) => {
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
                          "text-(--color-light) dark:text-(--color-dark)",
                          "bg-(--color-light)/10 dark:bg-(--color-dark)/10",
                          "border  border-(--color-light)/10 dark:border-(--color-dark)/10"
                        )}
                      >
                        <span>{project.slug.charAt(0).toUpperCase()}</span>
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
        <StatusBadge
          color={status.color}
          pingState="hidden"
          className="gap-1.5"
        >
          <status.Icon className="size-3.5 flex-none" />
          <span>{status.label}</span>
        </StatusBadge>
      </TableCell>
      <TableCell className="p-2">
        <time
          className="text-grey whitespace-nowrap"
          dateTime={new Date(token.created_at).toISOString()}
        >
          {createdAt.dateFormat},&nbsp;
          <span>{createdAt.hourFormat}</span>
        </time>
      </TableCell>
      <TableCell className="p-2">
        <time
          className="text-grey whitespace-nowrap"
          dateTime={new Date(token.expires_at).toISOString()}
        >
          {expiresAt.dateFormat},&nbsp;
          <span>{expiresAt.hourFormat}</span>
        </time>
      </TableCell>
      <TableCell className="p-2">{token.created_by.username}</TableCell>
      <TableCell className="p-2">
        {token.is_active && <RevokeTokenFormDialog token={token} />}
      </TableCell>
    </TableRow>
  );
}

function RevokeTokenFormDialog({ token }: { token: WorkspaceApiToken }) {
  const fetcher = useFetcher<typeof clientAction>();

  return (
    <SimpleConfirmationDialog
      fetcher={fetcher}
      title="Revoke this token ?"
      message={
        <>
          This action <strong>CANNOT</strong> be undone. Any script or CI
          pipeline using&nbsp;
          <Code className="bg-gray-700 text-white dark:bg-gray-300 dark:text-black">
            {token.masked_token}
          </Code>
          &nbsp;will immediately stop working.
        </>
      }
      form={
        <fetcher.Form method="post">
          <input type="hidden" name="token_id" value={token.id} />
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
                  <span className="sr-only">Revoke token</span>
                  <Trash2Icon className="flex-none size-4" />
                </Button>
              </DialogTrigger>
            </TooltipTrigger>
            <TooltipContent>Revoke token</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      }
    />
  );
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  const formData = await request.formData();
  const token_id = formData.get("token_id")?.toString()!;

  const { error } = await apiClient.POST(
    "/api/workspace/tokens/{token_id}/revoke/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: { token_id }
      }
    }
  );

  if (error) {
    const fullErrorMessage = error.errors.map((err) => err.detail).join(" ");
    toast.error("Error", {
      description: fullErrorMessage,
      closeButton: true
    });
    return { errors: error };
  }

  toast.success("Success", {
    description: "Token revoked successfully",
    closeButton: true
  });

  await queryClient.invalidateQueries(apiTokenQueries.list(workspaceId));
  return { data: null };
}
