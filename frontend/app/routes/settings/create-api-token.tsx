import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  CheckIcon,
  ChevronsUpDownIcon,
  InfoIcon,
  LoaderIcon
} from "lucide-react";
import * as React from "react";
import {
  Form,
  Link,
  href,
  useActionData,
  useLoaderData,
  useNavigation
} from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import type { Project, WorkspaceRoleName } from "~/api/types";
import { Code } from "~/components/code";
import { CopyButton } from "~/components/copy-button";
import { MultiSelect } from "~/components/multi-select";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
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
import { TOKEN_SCOPE_MAPPING, WORKSPACE_ROLE_MAPPING } from "~/lib/constants";
import { apiTokenQueries, ensureMinRole, projectQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  cn,
  formattedTime,
  getCsrfTokenHeader,
  getFormErrorsFromResponseData,
  metaTitle,
  pluralize,
  relativeTimeFormatter,
  stringToColor
} from "~/lib/utils";
import {
  getCurrentWorkspace,
  useCurrentWorkspace,
  useCurrentWorkspaceMembership
} from "~/lib/workspace-store";
import type { Route } from "./+types/create-api-token";

export function meta() {
  return [metaTitle("New API Token")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({}: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  await ensureMinRole(queryClient, "Member");

  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  const projects = await queryClient.ensureQueryData(
    projectQueries.list({ workspaceId })
  );

  return { projects };
}

export default function CreateApiTokenPage({
  actionData
}: Route.ComponentProps) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">New API Token</h2>
      </div>
      <Separator />

      {actionData?.data ? (
        <TokenCreatedCard data={actionData.data} />
      ) : (
        <>
          <h3 className="text-grey">
            Enter the details for the new token. The full token is only shown
            once, right after creation.
          </h3>
          <CreateApiTokenForm />
        </>
      )}
    </div>
  );
}

type TokenCreatedCardProps = {
  data: NonNullable<NonNullable<Route.ComponentProps["actionData"]>["data"]>;
};

function TokenCreatedCard({ data }: TokenCreatedCardProps) {
  return (
    <Card className="px-0">
      <CardHeader className="">
        <CardTitle className="flex gap-2 items-center text-lg">
          Token created <CheckIcon className="text-teal-500 size-5 flex-none" />
        </CardTitle>
        <p className="text-grey">
          Copy this token now. For security reasons, you won't be able to see it
          again.
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        <Separator className="mb-5" />

        <dl className="mt-4">
          <div className="flex items-center gap-2">
            <dt className="text-grey">Name:</dt>
            <dd>{data.name}</dd>
          </div>
          <div className="flex items-center gap-2">
            <dt className="text-grey">Role:</dt>
            <dd>{data.role_name}</dd>
          </div>
          <div className="flex items-center gap-2">
            <dt className="text-grey">Expires:</dt>
            <dd>
              <time dateTime={data.expires_at}>
                {formattedTime(data.expires_at)}&nbsp;
                <span className="text-grey">
                  ({relativeTimeFormatter(data.expires_at)})
                </span>
              </time>
            </dd>
          </div>
        </dl>

        <div className="flex items-center gap-2 w-full">
          <Code className="grow px-3 py-2 overflow-x-auto whitespace-nowrap">
            {data.token}
          </Code>
          <CopyButton
            value={data.token}
            label="Copy token"
            variant="outline"
            className="!opacity-100 flex-none"
          />
        </div>

        <p className="text-grey text-sm mt-4">
          Use it in the <Code>Authorization</Code> header of your requests:
        </p>
        <Code className="px-3 py-2 overflow-x-auto whitespace-nowrap">
          Authorization: Bearer {data.token}
        </Code>

        <Button asChild className="mt-6 w-fit">
          <Link to={href("/workspace/settings/api-tokens")}>Done</Link>
        </Button>
      </CardContent>
    </Card>
  );
}

const TOKEN_EXPIRY_OPTIONS = [7, 30, 60, 90, 180, 365] as const;
const DEFAULT_TOKEN_EXPIRY_DAYS = 30;

function CreateApiTokenForm() {
  const loaderData = useLoaderData<Route.ComponentProps["loaderData"]>();
  const actionData = useActionData<Route.ComponentProps["actionData"]>();

  const membership = useCurrentWorkspaceMembership();

  const errors = getFormErrorsFromResponseData(actionData?.errors);

  const workspaceId = useCurrentWorkspace().id;
  const { data: projects } = useQuery({
    ...projectQueries.list({ workspaceId }),
    initialData: loaderData.projects
  });

  const navigation = useNavigation();
  const isPending =
    navigation.state === "loading" || navigation.state === "submitting";

  const [selectedRole, setSelectedRole] =
    React.useState<WorkspaceRoleName>("Member");
  const [selectedScopes, setSelectedScopes] = React.useState<string[]>([]);
  const [selectedProjects, setSelectedProjects] = React.useState<Project[]>([]);

  const workspaceRoleOptions = Object.entries(WORKSPACE_ROLE_MAPPING).filter(
    ([, role]) => role.value <= membership.role
  );

  const selectedRoleValue = WORKSPACE_ROLE_MAPPING[selectedRole].value;

  return (
    <Form
      method="POST"
      className="flex flex-col gap-4 items-start w-full lg:w-4/5"
    >
      {errors.non_field_errors && (
        <Alert variant="destructive">
          <AlertCircleIcon className="size-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errors.non_field_errors}</AlertDescription>
        </Alert>
      )}

      <FieldSet
        errors={errors.name}
        name="name"
        required
        className="w-full flex flex-col gap-1"
      >
        <FieldSetLabel className="flex items-center gap-0.5">
          Name
        </FieldSetLabel>
        <FieldSetInput autoFocus placeholder="ex: CI pipeline" />
      </FieldSet>

      <input type="hidden" value={selectedRoleValue} name="role" />

      <Alert variant="info" className="bg-link/10 my-1 w-full">
        <InfoIcon className="size-4" />
        <AlertTitle>
          <span className="font-normal">Selected Role:</span>{" "}
          <span className="text-card-foreground">{selectedRole}</span>
        </AlertTitle>
        <AlertDescription className="mt-3 text-card-foreground">
          {WORKSPACE_ROLE_MAPPING[selectedRole].description}
        </AlertDescription>
      </Alert>

      <FieldSet name="role_value" errors={errors.role} className="w-full">
        <FieldSetLabel>Role</FieldSetLabel>

        <FieldSetSelect
          value={selectedRole}
          onValueChange={(role) => setSelectedRole(role as WorkspaceRoleName)}
        >
          <SelectTrigger
            id="role"
            className={cn(
              "w-full gap-2 [&_[data-summary]]:hidden [&>span]:inline [&>span]:whitespace-nowrap",
              "md:[&_[data-summary]]:inline"
            )}
          >
            <SelectValue placeholder="Select role" />
          </SelectTrigger>
          <SelectContent className="max-w-96 w-[var(--radix-select-trigger-width)]">
            {workspaceRoleOptions.map(([roleName, role]) => (
              <SelectItem
                value={roleName}
                key={roleName}
                className="w-full inline-flex"
              >
                <span className="font-medium" data-label>
                  {roleName}
                </span>
                <span className="text-grey" data-summary>
                  &nbsp;&middot;&nbsp;{role.summary}
                </span>
              </SelectItem>
            ))}
          </SelectContent>
        </FieldSetSelect>
      </FieldSet>

      {selectedScopes.map((scope) => (
        <input type="hidden" key={scope} name="scopes" value={scope} />
      ))}

      <div className="flex flex-col gap-1 w-full">
        <label htmlFor="scopes" className="text-sm font-medium">
          Scopes
        </label>
        <p className="text-grey text-sm">
          Leave empty to allow every scope the role permits.
        </p>

        <MultiSelect
          value={selectedScopes}
          className="w-full border-input"
          options={Object.entries(TOKEN_SCOPE_MAPPING).map(
            ([scope, definition]) => ({
              label: (
                <li key={scope} className="flex flex-col text-sm">
                  <span className="font-mono">{scope}</span>
                  <span className="text-grey text-xs">
                    {definition.description}
                  </span>
                </li>
              ),
              value: scope
            })
          )}
          popoverClassName="[&_[cmdk-list]]:max-w-(--radix-popover-content-available-width) !w-(--radix-popover-trigger-width)"
          Icon={ChevronsUpDownIcon}
          id="scopes"
          sideOffset={4}
          align="center"
          label="Scopes"
          order="label-icon"
          onValueChange={setSelectedScopes}
          aria-describedby="scopes-error"
          aria-invalid={!!errors.scopes}
        />

        {errors.scopes && (
          <span id="scopes-error" className="text-red-500 text-sm">
            {errors.scopes}
          </span>
        )}
      </div>

      {selectedProjects.map((project) => (
        <input
          type="hidden"
          key={project.id}
          name="accessible_project_ids"
          value={project.id}
        />
      ))}

      <div className="flex flex-col gap-1 w-full">
        <label htmlFor="accessible_projects" className="text-sm font-medium">
          Accessible projects
        </label>
        <p className="text-grey text-sm">
          Leave empty to give access to every project in the workspace.
        </p>

        <MultiSelect
          value={selectedProjects.map((project) => project.slug)}
          className="w-full border-input"
          options={projects.map((project) => {
            const projectColor = stringToColor(project.slug);
            return {
              label: (
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
              ),
              value: project.slug
            };
          })}
          popoverClassName="[&_[cmdk-list]]:max-w-(--radix-popover-content-available-width) !w-(--radix-popover-trigger-width)"
          Icon={ChevronsUpDownIcon}
          id="accessible_projects"
          sideOffset={4}
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
          <span id="accessible_projects-error" className="text-red-500 text-sm">
            {errors.accessible_project_ids}
          </span>
        )}
      </div>

      <FieldSet
        name="expires_in_days"
        className="w-full"
        errors={errors.expires_at}
      >
        <FieldSetLabel htmlFor="expires_in_days">Expires in</FieldSetLabel>

        <FieldSetSelect defaultValue={DEFAULT_TOKEN_EXPIRY_DAYS.toString()}>
          <SelectTrigger id="expires_in_days" className="w-full gap-2">
            <SelectValue placeholder="Select duration" />
          </SelectTrigger>
          <SelectContent>
            {TOKEN_EXPIRY_OPTIONS.map((days) => (
              <SelectItem value={days.toString()} key={days}>
                {days} {pluralize("day", days)}
              </SelectItem>
            ))}
          </SelectContent>
        </FieldSetSelect>
      </FieldSet>

      <SubmitButton isPending={isPending}>
        {isPending ? (
          <>
            Creating Token... <LoaderIcon size={15} className="animate-spin" />
          </>
        ) : (
          <>Create Token</>
        )}
      </SubmitButton>
    </Form>
  );
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  const formData = await request.formData();

  type Body = RequestInput<"post", "/api/workspace/tokens/">;

  const expiresInDays = Number(formData.get("expires_in_days")?.toString());

  const userData = {
    name: formData.get("name")?.toString() ?? "",
    role: Number(formData.get("role")?.toString()) as Body["role"],
    scopes: formData
      .getAll("scopes")
      .map((entry) => entry.toString()) as Body["scopes"],
    accessible_project_ids: formData
      .getAll("accessible_project_ids")
      .map((entry) => entry.toString()),
    expires_at:
      Number.isFinite(expiresInDays) && expiresInDays > 0
        ? new Date(
            Date.now() + expiresInDays * 24 * 60 * 60 * 1000
          ).toISOString()
        : undefined
  } satisfies Body;

  const { error: errors, data } = await apiClient.POST(
    "/api/workspace/tokens/",
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
      data: undefined
    };
  }

  toast.success("Success", {
    dismissible: true,
    closeButton: true,
    description: "API token created successfully"
  });
  await queryClient.invalidateQueries(apiTokenQueries.list(workspaceId));

  return {
    errors,
    data
  };
}
