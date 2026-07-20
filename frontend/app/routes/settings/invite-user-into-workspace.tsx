import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  CheckIcon,
  ChevronsUpDownIcon,
  LoaderIcon
} from "lucide-react";
import React from "react";
import {
  Form,
  href,
  useActionData,
  useLoaderData,
  useNavigation
} from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import type { Project, WorkspaceRoleName } from "~/api/types";
import { CopyButton } from "~/components/copy-button";
import { MultiSelect } from "~/components/multi-select";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { SubmitButton } from "~/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "~/components/ui/card";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel,
  FieldSetSelect
} from "~/components/ui/fieldset";
import {
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "~/components/ui/select";
import { Separator } from "~/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import {
  getCurrentWorkspace,
  useCurrentWorkspace,
  useCurrentWorkspaceMembership
} from "~/lib/auth-store";
import { WORKSPACE_ROLE_MAPPING } from "~/lib/constants";
import { ensureMinRole, projectQueries, workspaceQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  formattedTime,
  getCsrfTokenHeader,
  getFormErrorsFromResponseData,
  metaTitle,
  pluralize
} from "~/lib/utils";
import type { Route } from "./+types/invite-user-into-workspace";

export function meta() {
  return [
    metaTitle("Invite New User")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({}: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  await ensureMinRole(queryClient, "Admin");

  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  const projects = await queryClient.ensureQueryData(
    projectQueries.list({
      workspaceId
    })
  );

  return {
    projects
  };
}

export default function InviteUserIntoWorkspacePage({
  actionData
}: Route.ComponentProps) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Invite User into workspace</h2>
      </div>
      <Separator />

      {actionData?.data ? (
        <UserInvitationLinkCard data={actionData?.data} />
      ) : (
        <>
          <h3 className="text-grey">Enter the details for the new user</h3>
          <InviteNewUserForm />
        </>
      )}
    </div>
  );
}

type UserInvitationLinkCardProps = {
  data: NonNullable<NonNullable<Route.ComponentProps["actionData"]>["data"]>;
};

function UserInvitationLinkCard({ data }: UserInvitationLinkCardProps) {
  const registerLink =
    window.location.origin + href("/invite/:token", { token: data.token });

  return (
    <Card className="px-0">
      <CardHeader className="">
        <CardTitle className="flex gap-2 items-center text-lg">
          User Invited <CheckIcon className="text-teal-500 size-5 flex-none" />
        </CardTitle>
        <p className="text-grey">
          The user has been invited. Share the link below with them so they can
          accept the invitation.
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-2 ">
        <Separator className="mb-5" />

        <dl>
          <div className="flex items-center gap-2">
            <dt className="text-grey">Link:</dt>
            <dd className="flex items-center gap-2 grow max-w-[90%]">
              <a
                href={registerLink}
                target="_blank"
                className="text-link  hover:underline inline-flex min-w-0 items-center max-w-min"
                rel="noopener"
              >
                <p className="whitespace-nowrap text-ellipsis overflow-x-hidden max-w-full">
                  {registerLink}
                </p>
              </a>
              <TooltipProvider>
                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <CopyButton
                      value={registerLink}
                      label="Copy url"
                      size="icon"
                      className="hover:bg-transparent !opacity-100 size-4 flex-none"
                    />
                  </TooltipTrigger>
                  <TooltipContent>Copy URL</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </dd>
          </div>

          <div className="flex gap-2 items-center">
            <dt className="text-grey">Valid until:</dt>
            <dd>
              <time dateTime={data.expires_at}>
                {formattedTime(data.expires_at)}
              </time>
            </dd>
          </div>

          <div className="flex gap-2 items-center">
            <dt className="text-grey">Username:</dt>
            <dd>{data.username}</dd>
          </div>

          <div className="flex gap-2 items-center">
            <dt className="text-grey">Role:</dt>
            <dd>{data.role_name}</dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  );
}

function InviteNewUserForm() {
  const loaderData = useLoaderData<Route.ComponentProps["loaderData"]>();
  const actionData = useActionData<Route.ComponentProps["actionData"]>();

  const membership = useCurrentWorkspaceMembership();

  const errors = getFormErrorsFromResponseData(actionData?.errors);

  const workspaceId = useCurrentWorkspace().id;
  const { data: projects } = useQuery({
    ...projectQueries.list({
      workspaceId
    }),
    initialData: loaderData.projects
  });

  const navigation = useNavigation();
  const isPending =
    navigation.state === "loading" || navigation.state === "submitting";

  const [selectedRole, setSelectedRole] =
    React.useState<WorkspaceRoleName>("Guest");

  const [selectedProjects, setSelectedProjects] = React.useState<Project[]>([]);
  const validForOptions = Array.from({ length: 7 }, (_, i) => i + 1);
  const excludedRoles = ["Owner"];
  if (membership.role_name === "Admin") {
    excludedRoles.push("Admin");
  }

  const workspaceRoleOptions = Object.entries(WORKSPACE_ROLE_MAPPING).filter(
    ([roleName]) => {
      return !excludedRoles.includes(roleName);
    }
  );

  const selectedRoleValue = WORKSPACE_ROLE_MAPPING[selectedRole];

  return (
    <Form
      method="POST"
      className="flex flex-col gap-4 items-start w-full lg:w-4/5"
    >
      {errors.non_field_errors && (
        <Alert variant="destructive">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errors.non_field_errors}</AlertDescription>
        </Alert>
      )}

      <div className="flex items-start gap-4 w-full">
        <FieldSet
          errors={errors.username}
          name="username"
          required
          className="w-full"
        >
          <FieldSetLabel className="flex items-center gap-0.5">
            Username
          </FieldSetLabel>

          <FieldSetInput autoFocus placeholder="ex: johndoe" />
        </FieldSet>

        <input type="hidden" value={selectedRoleValue} name="role" />

        <FieldSet name="role_value" errors={errors.role}>
          <FieldSetLabel>Role</FieldSetLabel>

          <FieldSetSelect
            value={selectedRole}
            onValueChange={(role) => setSelectedRole(role as WorkspaceRoleName)}
          >
            <SelectTrigger id="role" className="w-32 gap-2">
              <SelectValue placeholder="Select role" />
            </SelectTrigger>
            <SelectContent>
              {workspaceRoleOptions.map(([roleName, roleValue]) => (
                <SelectItem value={roleName} key={roleValue}>
                  {roleName}
                </SelectItem>
              ))}
            </SelectContent>
          </FieldSetSelect>
        </FieldSet>
      </div>

      <FieldSet name="valid_for" className="w-full" errors={errors.valid_for}>
        <FieldSetLabel>Invitation Valid For</FieldSetLabel>

        <FieldSetSelect
          defaultValue={(3).toString()}
          onValueChange={(value) => {}}
        >
          <SelectTrigger className="w-full gap-2">
            <SelectValue placeholder="Select days" />
          </SelectTrigger>
          <SelectContent>
            {validForOptions.map((number) => (
              <SelectItem value={number.toString()} key={number}>
                {number} {pluralize("day", number)}
              </SelectItem>
            ))}
          </SelectContent>
        </FieldSetSelect>
      </FieldSet>

      {selectedProjects.map((project) => (
        <input
          type="hidden"
          key={project.id}
          name="accessible_project_ids"
          value={project.id}
        />
      ))}

      {selectedRole === "Guest" && (
        <div className="my-2 flex flex-col gap-1 w-full">
          <label htmlFor="accessible_projects" className="sr-only">
            Accessible projects
          </label>

          <MultiSelect
            value={selectedProjects.map((project) => project.slug)}
            className="w-full border-muted"
            options={projects.map((project) => project.slug)}
            Icon={ChevronsUpDownIcon}
            id="accessible_projects"
            sideOffset={4}
            popoverClassName="!w-(--radix-popover-trigger-width)"
            align="center"
            label="Accessible projects"
            order="label-icon"
            onValueChange={(newVal) => {
              setSelectedProjects(
                projects.filter((p) => newVal.includes(p.slug))
              );
            }}
            aria-describedby="accessible_projects-error"
            aria-invalid={!!errors.accessible_project_ids}
          />

          {errors.accessible_project_ids && (
            <span
              id="accessible_projects-error"
              className="text-red-500 text-sm"
            >
              {errors.accessible_project_ids}
            </span>
          )}
        </div>
      )}

      <SubmitButton isPending={isPending}>
        {isPending ? (
          <>
            Inviting User... <LoaderIcon size={15} className="animate-spin" />
          </>
        ) : (
          <>Invite User</>
        )}
      </SubmitButton>
    </Form>
  );
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  const formData = await request.formData();

  type Body = RequestInput<"post", "/api/workspace/invite-user/">;
  const userData = {
    username: formData.get("username")?.toString() ?? "",
    accessible_project_ids: formData
      .getAll("accessible_project_ids")
      .map((entry) => entry.toString()),
    role: Number(formData.get("role")?.toString()) as Body["role"],
    valid_for: Number(
      formData.get("valid_for")?.toString()
    ) as Body["valid_for"]
  } satisfies Body;

  const { error: errors, data } = await apiClient.POST(
    "/api/workspace/invite-user/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      body: userData
    }
  );

  if (errors) {
    return {
      errors,
      data
    };
  }
  toast.success("Success", {
    dismissible: true,
    closeButton: true,
    description: `${userData.username} has been invited to the workspace`
  });
  await queryClient.invalidateQueries({
    queryKey: workspaceQueries.invitations(workspaceId).queryKey.slice(0, 3)
  });

  return {
    errors,
    data
  };
}
