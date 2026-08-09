import { useQuery } from "@tanstack/react-query";
import { useDebounce } from "@uidotdev/usehooks";
import { Command as CommandPrimitive } from "cmdk";
import {
  AlertCircleIcon,
  CheckIcon,
  ChevronDownIcon,
  ChevronsRightIcon,
  FlameIcon,
  InfoIcon,
  LoaderIcon,
  SearchIcon,
  Trash2Icon
} from "lucide-react";
import * as React from "react";
import { href, redirect, useFetcher } from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import { DeleteConfirmationDialog } from "~/components/delete-confirmation-dialog";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandItem,
  CommandList
} from "~/components/ui/command";
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
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from "~/components/ui/popover";
import { Separator } from "~/components/ui/separator";
import {
  adminWorkspaceQueries,
  serverUserQueries,
  userQueries
} from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  type ErrorResponseFromAPI,
  cn,
  getCsrfTokenHeader,
  getFormErrorsFromResponseData,
  metaTitle
} from "~/lib/utils";
import type { Route } from "./+types/workspace-details";

export function meta() {
  return [
    metaTitle("Workspace Settings")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({}: Route.ClientLoaderArgs) {
  return;
}

export default function WorkspaceDetailsPage({
  matches: {
    "3": { loaderData }
  },
  params
}: Route.ComponentProps) {
  const { data: workspace } = useQuery({
    ...adminWorkspaceQueries.single(params.workspaceId),
    initialData: loaderData.workspace
  });

  const owner = workspace.members.find(
    (member) => member.role_name === "Owner"
  );

  return (
    <section className="flex flex-col gap-4">
      <h3 className="text-grey">Update the details of this workspace</h3>

      <div className="grid lg:grid-cols-12 gap-10 relative">
        <div className="lg:col-span-10 flex flex-col">
          <section id="details" className="flex gap-1 scroll-mt-20">
            <div className="w-16 hidden md:flex flex-col items-center">
              <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
                <InfoIcon size={15} className="flex-none text-grey" />
              </div>
              <div className="h-full border border-grey/50"></div>
            </div>

            <div className="w-full flex flex-col gap-5 pt-1 pb-8">
              <h2 className="text-lg text-grey">Details</h2>

              <WorkspaceDetailsForm name={workspace.name} />
            </div>
          </section>

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
                    <h3 className="text-lg font-medium">Transfer Ownership</h3>
                    <p>
                      Transfer ownership of this workspace to another user of
                      this server
                    </p>
                  </div>
                  <TransferOwnershipForm
                    currentOwnerUsername={owner?.user.username}
                  />
                </div>

                <Separator />

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
              </div>
            </div>
          </section>
        </div>
      </div>
    </section>
  );
}

async function updateWorkspace(workspaceId: string, formData: FormData) {
  const queryClient = getQueryClient();

  const userData = {
    name: formData.get("name")?.toString() ?? ""
  } satisfies RequestInput<"put", "/api/console/workspaces/{id}/">;

  const apiResponse = await apiClient.PUT("/api/console/workspaces/{id}/", {
    headers: {
      ...(await getCsrfTokenHeader())
    },
    params: {
      path: { id: workspaceId }
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
    queryClient.invalidateQueries({
      queryKey: adminWorkspaceQueries.single(workspaceId).queryKey.slice(0, 1)
    }),
    queryClient.invalidateQueries(userQueries.authedUser),
    queryClient.invalidateQueries(userQueries.memberships)
  ]);
  toast.success("Workspace updated successfully!", { closeButton: true });

  return {
    userData,
    errors: apiResponse.error
  };
}

async function archiveWorkspace(workspaceId: string, formData: FormData) {
  const queryClient = getQueryClient();

  const workspace = await queryClient.ensureQueryData(
    adminWorkspaceQueries.single(workspaceId)
  );

  if (formData.get("workspace_name")?.toString().trim() !== workspace.name) {
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

  const apiResponse = await apiClient.DELETE("/api/console/workspaces/{id}/", {
    headers: {
      ...(await getCsrfTokenHeader())
    },
    params: {
      path: { id: workspaceId }
    }
  });

  if (apiResponse.error) {
    return {
      errors: apiResponse.error
    };
  }

  await Promise.all([
    queryClient.invalidateQueries({
      queryKey: adminWorkspaceQueries.single(workspaceId).queryKey.slice(0, 1)
    }),
    queryClient.invalidateQueries(userQueries.authedUser),
    queryClient.invalidateQueries(userQueries.memberships)
  ]);

  toast.success("Success", {
    closeButton: true,
    description: (
      <span>
        Workspace <strong>{workspace.name}</strong> has been deleted.
      </span>
    )
  });
  throw redirect(href("/admin/workspaces"));
}

async function transferWorkspaceOwnership(
  workspaceId: string,
  formData: FormData
) {
  const queryClient = getQueryClient();

  const workspace = await queryClient.ensureQueryData(
    adminWorkspaceQueries.single(workspaceId)
  );

  const userData = {
    owner_id: Number(formData.get("owner_id")?.toString() ?? "")
  } satisfies RequestInput<
    "put",
    "/api/console/workspaces/{id}/transfer-ownership/"
  >;

  const apiResponse = await apiClient.PUT(
    "/api/console/workspaces/{id}/transfer-ownership/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: { id: workspaceId }
      },
      body: userData
    }
  );

  if (apiResponse.error) {
    return {
      userData,
      errors: apiResponse.error
    };
  }

  await Promise.all([
    queryClient.invalidateQueries({
      queryKey: adminWorkspaceQueries.single(workspaceId).queryKey.slice(0, 1)
    }),
    queryClient.invalidateQueries(userQueries.authedUser),
    queryClient.invalidateQueries(userQueries.memberships)
  ]);
  toast.success("Success", {
    closeButton: true,
    description: (
      <span>
        Ownership of workspace `<strong>{workspace.name}</strong>` has been
        successfully transferred.
      </span>
    )
  });

  return {
    userData,
    errors: apiResponse.error
  };
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const formData = await request.formData();
  const intent = formData.get("intent")?.toString();

  switch (intent) {
    case "update_workspace": {
      return updateWorkspace(params.workspaceId, formData);
    }
    case "archive_workspace": {
      return archiveWorkspace(params.workspaceId, formData);
    }
    case "transfer_workspace_ownership": {
      return transferWorkspaceOwnership(params.workspaceId, formData);
    }
    default: {
      throw new Error(`Unexpected intent \`${intent}\``);
    }
  }
}

type WorkspaceDetailsFormProps = {
  name: string;
};

function WorkspaceDetailsForm({ name }: WorkspaceDetailsFormProps) {
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
        />
      </FieldSet>

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

type TransferOwnershipFormProps = {
  currentOwnerUsername?: string;
};

function TransferOwnershipForm({
  currentOwnerUsername
}: TransferOwnershipFormProps) {
  const [isOpen, setIsOpen] = React.useState(false);

  const fetcher = useFetcher<typeof clientAction>();
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const selectOwnerBtnRef = React.useRef<React.ComponentRef<"button">>(null);
  const [data, setData] = React.useState(fetcher.data);
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(data?.errors);
  const [isPopoverOpen, setPopoverOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");

  const debouncedQuery = useDebounce(query, 300);

  const { data: usersResponse } = useQuery(
    serverUserQueries.list({
      is_active: true,
      query: debouncedQuery
    })
  );

  const userList = (usersResponse?.results ?? []).filter(
    (user) => user.username !== currentOwnerUsername
  );

  const [selectedOwner, setSelectedOwner] = React.useState<
    (typeof userList)[number] | null
  >(null);

  React.useEffect(() => {
    setData(fetcher.data);

    // only focus on the correct input in case of error
    if (fetcher.state === "idle" && fetcher.data) {
      if (!fetcher.data.errors) {
        formRef.current?.reset();
        setIsOpen(false);
      } else {
        selectOwnerBtnRef.current?.focus();
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetcher.state, fetcher.data]);

  const close = React.useCallback(() => {
    setIsOpen(false);
    setData(undefined);
    setQuery("");
    setSelectedOwner(null);
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
              This will transfer ownership to the selected user and downgrade
              the current owner to an admin.
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
          <fieldset className="flex flex-col gap-2 flex-1">
            <label htmlFor="owner_id">New owner</label>
            <small className="text-grey">
              Any active user of this server can be selected, they will be added
              to the workspace if they are not already a member
            </small>

            {selectedOwner && (
              <input type="hidden" name="owner_id" value={selectedOwner.id} />
            )}

            <Popover open={isPopoverOpen} onOpenChange={setPopoverOpen}>
              <PopoverTrigger asChild>
                <Button
                  ref={selectOwnerBtnRef}
                  variant="outline"
                  type="button"
                  className="justify-between"
                  aria-describedby="new-owner-error"
                  aria-invalid={!!errors.owner_id}
                >
                  {selectedOwner ? (
                    <span className="whitespace-nowrap">
                      <span>{selectedOwner.first_name}</span>
                      &nbsp;
                      <span>&middot;</span>
                      &nbsp;
                      <span className="text-grey text-xs">
                        {selectedOwner.username}
                      </span>
                    </span>
                  ) : (
                    <span className="text-sm">Select new owner</span>
                  )}
                  <ChevronDownIcon className="size-4 flex-none" />
                </Button>
              </PopoverTrigger>
              <PopoverContent
                className={cn(
                  "!w-(--radix-popover-trigger-width) p-0 z-999 shadow-md rounded-lg",
                  "[&_[data-slot='command-list-wrapper']_*]:static",
                  "[&_[data-slot='command-input-wrapper']]:px-2"
                )}
                align="center"
              >
                <Command shouldFilter={false} className="w-full">
                  <div className="flex px-3 py-3.5 items-center gap-1">
                    <SearchIcon className="size-4 flex-none text-grey" />
                    <CommandPrimitive.Input
                      placeholder="Search users"
                      className="text-sm bg-inherit focus-visible:outline-hidden px-2 w-42"
                      onValueChange={setQuery}
                      value={query}
                    />
                  </div>
                  <hr className="w-full border-border" />
                  <CommandList className="flex flex-col gap-2 min-w-32 md:min-w-42 w-full bg-transparent border-none">
                    <CommandEmpty>No active users found.</CommandEmpty>

                    {userList.map((user) => {
                      const isSelected = user.id === selectedOwner?.id;

                      return (
                        <CommandItem
                          key={user.id}
                          value={user.id.toString()}
                          onSelect={() => {
                            setSelectedOwner(user);
                            setQuery("");
                            setPopoverOpen(false);
                          }}
                          className="cursor-pointer flex gap-1.5"
                        >
                          <div className="flex items-center justify-between w-full gap-4">
                            <span className="whitespace-nowrap">
                              <span>{user.first_name}</span>
                              &nbsp;
                              <span>&middot;</span>
                              &nbsp;
                              <span className="text-grey text-xs">
                                {user.username}
                              </span>
                            </span>

                            <span className="flex size-4 items-center justify-center flex-none py-2.5">
                              {isSelected && (
                                <CheckIcon className="size-4 text-grey" />
                              )}
                            </span>
                          </div>
                        </CommandItem>
                      );
                    })}
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>

            {errors.owner_id && (
              <span id="new-owner-error" className="text-red-500 text-sm">
                {errors.owner_id}
              </span>
            )}
          </fieldset>
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
