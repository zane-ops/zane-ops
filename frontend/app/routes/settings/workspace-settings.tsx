import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  CheckIcon,
  ChevronsRightIcon,
  FlameIcon,
  InfoIcon,
  LoaderIcon,
  Trash2Icon
} from "lucide-react";
import * as React from "react";
import { href, redirect, useFetcher, useMatches } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { DeleteConfirmationDialog } from "~/components/delete-confirmation-dialog";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "~/components/ui/dialog";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel,
  FieldSetSelect
} from "~/components/ui/fieldset";
import {
  type Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "~/components/ui/select";
import { Separator } from "~/components/ui/separator";
import { userQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  type ErrorResponseFromAPI,
  cn,
  getFormErrorsFromResponseData,
  notFound
} from "~/lib/utils";
import { getCsrfTokenHeader, hasMinRole, metaTitle } from "~/utils";
import type { Route } from "./+types/workspace-settings";

export function meta() {
  return [
    metaTitle("Workspace Settings")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({}: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();

  const workspace = await queryClient.ensureQueryData(
    userQueries.currentWorkspace
  );
  if (!workspace) {
    throw notFound("Oops !");
  }
  return { workspace };
}

export default function WorkspaceSettingsPage({
  loaderData,
  matches: {
    "1": {
      loaderData: { user }
    }
  }
}: Route.ComponentProps) {
  const { data: workspace } = useQuery({
    ...userQueries.currentWorkspace,
    initialData: loaderData.workspace
  });

  if (!workspace) return null;

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-2xl">Workspace Settings</h2>
      <Separator />
      <h3 className="text-grey">
        Update the general details of your workspace
      </h3>

      <div className="grid lg:grid-cols-12 gap-10 relative">
        <div className="lg:col-span-10 flex flex-col">
          <section id="details" className="flex gap-1 scroll-mt-20">
            <div className="w-16 hidden md:flex flex-col items-center">
              <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
                <InfoIcon size={15} className="flex-none text-grey" />
              </div>
              {hasMinRole(user, "Owner") && (
                <div className="h-full border border-grey/50"></div>
              )}
            </div>

            <div className="w-full flex flex-col gap-5 pt-1 pb-8">
              <h2 className="text-lg text-grey">Details</h2>

              <WorkspaceDetailsForm name={workspace.name} />
            </div>
          </section>

          {hasMinRole(user, "Owner") && (
            <section id="danger" className="flex gap-1 scroll-mt-20">
              <div className="w-16 hidden md:flex flex-col items-center">
                <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-red-500">
                  <FlameIcon size={15} className="flex-none text-red-500" />
                </div>
              </div>
              <div className="w-full flex flex-col gap-5 pt-1 pb-14">
                <h2 className="text-lg text-red-400">Danger Zone</h2>
                <div className="flex flex-col gap-4 items-start max-w-4xl w-full rounded-md border border-border py-4">
                  <div className="flex md:flex-row gap-4 justify-between items-center w-full px-4">
                    <div className="flex flex-col gap-1">
                      <h3 className="text-lg font-medium">Delete workspace</h3>
                      <p>
                        Deletes this workspace along with all its project and
                        services
                      </p>
                    </div>
                    <WorkspaceDeleteForm name={workspace.name} />
                  </div>
                  <Separator />

                  <div className="flex md:flex-row gap-4 justify-between items-center w-full px-4">
                    <div className="flex flex-col gap-1">
                      <h3 className="text-lg font-medium">
                        Transfer Ownership
                      </h3>
                      <p>
                        Transfer ownership of this workspace to another member
                      </p>
                    </div>
                    <TransferOwnershipForm />
                  </div>
                </div>
              </div>
            </section>
          )}
        </div>
      </div>
    </section>
  );
}

async function updateWorkspace(formData: FormData) {
  const queryClient = getQueryClient();
  const userData = {
    name: formData.get("name")?.toString() ?? ""
  };
  const apiResponse = await apiClient.PUT("/api/workspace/", {
    headers: {
      ...(await getCsrfTokenHeader())
    },
    body: userData
  });

  if (apiResponse.error) {
    return {
      userData,
      errors: apiResponse.error
    };
  }

  await Promise.all([
    queryClient.invalidateQueries(userQueries.currentWorkspace),
    queryClient.invalidateQueries(userQueries.memberships)
  ]);
  toast.success("Workspace updated successfully!", { closeButton: true });

  return {
    userData,
    errors: apiResponse.error
  };
}

async function archiveWorkspace(formData: FormData) {
  const queryClient = getQueryClient();

  const workspace = await queryClient.fetchQuery(userQueries.currentWorkspace);
  if (!workspace) {
    throw redirect("/");
  }

  if (formData.get("name")?.toString().trim() !== workspace.name) {
    return {
      errors: {
        type: "validation_error",
        errors: [
          {
            attr: "workspace_name",
            code: "invalid",
            detail: "The workspace name does not match"
          }
        ]
      } satisfies ErrorResponseFromAPI
    };
  }

  const apiResponse = await apiClient.DELETE("/api/workspace/", {
    headers: {
      ...(await getCsrfTokenHeader())
    }
  });

  if (apiResponse.error) {
    return {
      errors: apiResponse.error
    };
  }

  await Promise.all([
    queryClient.invalidateQueries(userQueries.currentWorkspace),
    queryClient.invalidateQueries(userQueries.memberships)
  ]);

  toast.success("Success", {
    closeButton: true,
    description: (
      <span>
        Workspace `<strong>{workspace.name}</strong>` has been successfully
        deleted.
      </span>
    )
  });
  throw redirect(href("/"));
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const formData = await request.formData();
  const intent = formData.get("intent")?.toString();

  switch (intent) {
    case "update_workspace": {
      return updateWorkspace(formData);
    }
    case "archive_workspace": {
      return archiveWorkspace(formData);
    }
    default: {
      throw new Error("Unexpected intent");
    }
  }
}

type WorkspaceDetailsFormProps = {
  name: string;
};

function WorkspaceDetailsForm({ name }: WorkspaceDetailsFormProps) {
  const {
    "1": {
      loaderData: { user }
    }
  } = useMatches() as Route.ComponentProps["matches"];
  const fetcher = useFetcher<typeof clientAction>();
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  return (
    <fetcher.Form method="post" className="flex flex-col gap-4">
      {errors.non_field_errors && (
        <Alert variant="destructive">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errors.non_field_errors}</AlertDescription>
        </Alert>
      )}

      <FieldSet
        errors={errors.name}
        name="name"
        className="flex flex-col gap-1.5 flex-1"
      >
        <FieldSetLabel>Workspace name</FieldSetLabel>
        <FieldSetInput
          placeholder="ex: Default workspace"
          defaultValue={name}
          disabled={!hasMinRole(user, "Owner")}
        />
      </FieldSet>

      {hasMinRole(user, "Owner") && (
        <SubmitButton
          isPending={isPending}
          variant="secondary"
          className="self-start"
          name="intent"
          value="update_workspace"
        >
          {isPending ? (
            <>
              <LoaderIcon className="animate-spin" size={15} />
              <span>Updating ...</span>
            </>
          ) : (
            <>
              <CheckIcon size={15} className="flex-none" />
              <span>Update</span>
            </>
          )}
        </SubmitButton>
      )}
    </fetcher.Form>
  );
}

function WorkspaceDeleteForm({ name }: { name: string }) {
  const fetcher = useFetcher<typeof clientAction>();
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  const confirmMessage =
    "Deleting this workspace will permanently delete all its projects, along with their services and deployments. This action is irreversible.";

  return (
    <div className="flex flex-col gap-2 items-start">
      <DeleteConfirmationDialog
        fetcher={fetcher}
        title="Delete this workspace ?"
        message={confirmMessage}
        confirmationValue={name}
        confirmationFieldName="workspace_name"
        form={
          <fetcher.Form method="post">
            <FieldSet name="workspace_name" errors={errors.workspace_name}>
              <FieldSetInput />
            </FieldSet>
            <input type="hidden" name="intent" value="archive_workspace" />
          </fetcher.Form>
        }
        trigger={
          <DialogTrigger asChild>
            <Button
              variant="destructive"
              type="button"
              className={cn("inline-flex gap-1 items-center")}
            >
              <Trash2Icon size={15} className="flex-none" />
              <span>Delete this workspace</span>
            </Button>
          </DialogTrigger>
        }
      />
    </div>
  );
}

function TransferOwnershipForm() {
  const [isOpen, setIsOpen] = React.useState(false);

  const fetcher = useFetcher<typeof clientAction>();
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const selectTriggerRef =
    React.useRef<React.ComponentRef<typeof Select>>(null);
  const [data, setData] = React.useState(fetcher.data);
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(data?.errors);

  React.useEffect(() => {
    setData(fetcher.data);

    // only focus on the correct input in case of error
    if (fetcher.state === "idle" && fetcher.data) {
      if (!fetcher.data.errors) {
        formRef.current?.reset();
        setIsOpen(false);
      }
      // else if (focusFieldName) {
      //   (
      //     formRef.current?.elements.namedItem(
      //       focusFieldName
      //     ) as HTMLInputElement | null
      //   )?.focus();
      // }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetcher.state, fetcher.data]);

  const close = React.useCallback(() => {
    setIsOpen(false);
    setData(undefined);
  }, []);

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (isPending) return;
        setIsOpen(open);
        if (!open) close();
      }}
    >
      <DialogTrigger asChild>
        <Button
          variant="warning"
          className={cn("inline-flex gap-1 items-center")}
        >
          <span>Transfer</span>
          <ChevronsRightIcon size={15} className="flex-none" />
        </Button>
      </DialogTrigger>
      <DialogContent className="gap-0">
        <DialogHeader>
          <DialogTitle>Transfer ownership of this workspace</DialogTitle>

          <Alert variant="warning" className="my-5">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Warning</AlertTitle>
            <AlertDescription>
              This will transfer ownership to the selected member and downgrade
              you to an admin.
            </AlertDescription>
          </Alert>
        </DialogHeader>

        {errors.non_field_errors && (
          <Alert variant="destructive" className="my-2">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{errors.non_field_errors}</AlertDescription>
          </Alert>
        )}

        <fetcher.Form
          className="flex flex-col w-full mb-5 gap-4"
          method="post"
          id="transfer-ownership"
          ref={formRef}
        >
          <FieldSet
            name="new_owner_id"
            // errors={errors.new_owner_id}
            className="flex flex-col gap-2 flex-1"
            required
          >
            <FieldSetLabel htmlFor="new_owner_id">New owner</FieldSetLabel>
            <small className="text-grey">
              Only admins of this workspace can be selected
            </small>

            <FieldSetSelect>
              <SelectTrigger id="new_owner_id" ref={selectTriggerRef}>
                <SelectValue placeholder="Select new owner" />
              </SelectTrigger>
              <SelectContent className="z-999">
                {/* {environments.map((env) => (
                                <SelectItem value={env.name} key={env.id}>
                                  {env.name}
                                </SelectItem>
                              ))} */}
              </SelectContent>
            </FieldSetSelect>
          </FieldSet>
        </fetcher.Form>

        <DialogFooter className="-mx-6 px-6 pt-4 ">
          <div className="flex items-center gap-4 w-full">
            <SubmitButton
              className={cn("inline-flex gap-1 items-center")}
              value="transfer_workspace_ownership"
              name="intent"
              form="transfer-ownership"
              isPending={isPending}
            >
              {isPending ? (
                <>
                  <LoaderIcon className="animate-spin flex-none" size={15} />
                  <span>Transfering ...</span>
                </>
              ) : (
                <>
                  <span>Transfer</span>
                </>
              )}
            </SubmitButton>

            <Button variant="outline" onClick={close}>
              Cancel
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
