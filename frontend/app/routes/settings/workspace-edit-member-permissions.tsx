import { useQuery } from "@tanstack/react-query";
import { ChevronsUpDownIcon, LoaderIcon } from "lucide-react";
import * as React from "react";
import {
  Form,
  href,
  useActionData,
  useLoaderData,
  useNavigation
} from "react-router";
import { redirect } from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import type { Project, WorkspaceMember, WorkspaceRoleName } from "~/api/types";
import { MultiSelect } from "~/components/multi-select";
import { SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
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
import { WORKSPACE_ROLE_MAPPING } from "~/lib/constants";
import { ensureMinRole, projectQueries, workspaceQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  getCsrfTokenHeader,
  getFormErrorsFromResponseData,
  getUserDisplayName,
  hasMinRole,
  metaTitle
} from "~/lib/utils";
import {
  getCurrentWorkspace,
  useCurrentWorkspace,
  useCurrentWorkspaceMembership
} from "~/lib/workspace-store";
import type { Route } from "./+types/workspace-edit-member-permissions";

export function meta() {
  return [
    metaTitle("Edit Member Permissions")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  const authedUser = await ensureMinRole(queryClient, "Admin");
  const { id: workspaceId } = await getCurrentWorkspace(queryClient);

  const [member, projects] = await Promise.all([
    queryClient.ensureQueryData(
      workspaceQueries.member(workspaceId, params.id)
    ),
    queryClient.ensureQueryData(
      projectQueries.list({
        workspaceId
      })
    )
  ]);

  if (
    authedUser.membership?.id.toString() === params.id ||
    hasMinRole(member, "Owner") ||
    (hasMinRole(member, "Admin") &&
      authedUser.membership?.role_name === "Admin")
  ) {
    throw redirect(href("/workspace/settings/team"));
  }

  return {
    member,
    projects
  };
}

export default function EditWorkspaceMemberPermissionsPage({
  loaderData,
  params
}: Route.ComponentProps) {
  const workspace = useCurrentWorkspace();
  const { data: member } = useQuery({
    ...workspaceQueries.member(workspace.id, params.id),
    initialData: loaderData.member
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">
          Edit&nbsp;
          <strong className="text-grey font-medium">
            &ldquo;{member.user.username}&rdquo;
          </strong>
          &nbsp;permissions
        </h2>
      </div>
      <Separator />
      <h3 className="text-grey">
        Update the role and project access for the member
      </h3>
      <EditWorkspaceMemberForm member={member} />
    </div>
  );
}

type EditWorkspaceMemberFormProps = {
  member: WorkspaceMember;
};

function EditWorkspaceMemberForm({ member }: EditWorkspaceMemberFormProps) {
  const loaderData = useLoaderData<Route.ComponentProps["loaderData"]>();
  const actionData = useActionData<Route.ComponentProps["actionData"]>();
  const membership = useCurrentWorkspaceMembership();

  const navigation = useNavigation();
  const isPending =
    navigation.state === "loading" || navigation.state === "submitting";

  const workspaceId = useCurrentWorkspace().id;
  const { data: projects } = useQuery({
    ...projectQueries.list({
      workspaceId
    }),
    initialData: loaderData.projects
  });

  const [selectedRole, setSelectedRole] = React.useState<WorkspaceRoleName>(
    member.role_name
  );

  const [selectedProjects, setSelectedProjects] = React.useState<Project[]>(
    () => {
      const accessibleIds = new Set(
        member.accessible_projects.map((project) => project.id)
      );
      return projects.filter((project) => accessibleIds.has(project.id));
    }
  );

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
  const errors = getFormErrorsFromResponseData(actionData?.errors);

  return (
    <Form
      method="post"
      className="flex flex-col gap-4 items-start w-full lg:w-4/5"
    >
      <input type="hidden" value={selectedRoleValue} name="role" />
      {selectedProjects.map((project) => (
        <input
          type="hidden"
          key={project.id}
          name="accessible_project_ids"
          value={project.id}
        />
      ))}

      <FieldSet name="role_value" errors={errors.role} className="w-full">
        <FieldSetLabel>Role</FieldSetLabel>

        <FieldSetSelect
          value={selectedRole}
          onValueChange={(role) => setSelectedRole(role as WorkspaceRoleName)}
        >
          <SelectTrigger id="role" className="w-full gap-2">
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
            Updating permissions...{" "}
            <LoaderIcon size={15} className="animate-spin" />
          </>
        ) : (
          <>Update permissions</>
        )}
      </SubmitButton>
    </Form>
  );
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  const formData = await request.formData();

  type Body = RequestInput<
    "put",
    "/api/workspace/members/{membership_id}/permissions/"
  >;
  const userData = {
    accessible_project_ids: formData
      .getAll("accessible_project_ids")
      .map((entry) => entry.toString()),
    role: Number(formData.get("role")?.toString()) as Body["role"]
  } satisfies Body;

  const { error: errors, data } = await apiClient.PUT(
    "/api/workspace/members/{membership_id}/permissions/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          membership_id: params.id
        }
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
    description: (
      <p>
        <strong className="text-grey">
          &ldquo;{data.user.username}&rdquo;
        </strong>
        's permissions have been updated successfully.
      </p>
    )
  });
  await queryClient.invalidateQueries({
    queryKey: workspaceQueries.members(workspaceId).queryKey.slice(0, 3)
  });

  throw redirect(href("/workspace/settings/team"));
}
