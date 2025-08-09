import { useQuery } from "@tanstack/react-query";
import {
  BanIcon,
  CheckIcon,
  GithubIcon,
  GitlabIcon,
  InfoIcon,
  LoaderIcon,
  PencilLineIcon,
  Undo2Icon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { flushSync } from "react-dom";
import { useLoaderData } from "react-router";
import { Code } from "~/components/code";
import { GitRepositoryBranchListInput } from "~/components/git-repository-branch-list-input";
import { GitRepositoryListInput } from "~/components/git-repository-list-input";
import { Button } from "~/components/ui/button";
import { SubmitButton } from "~/components/ui/button";
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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { type Service, gitAppsQueries } from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import {
  useFetcherWithCallbacks,
  useServiceQuery
} from "~/routes/services/settings/service-settings";
import { type Route } from "../settings/+types/services-settings";

export type ServiceGitSourceFormProps = {
  service_slug: string;
  project_slug: string;
  env_slug: string;
};

export function ServiceGitSourceForm({
  service_slug,
  project_slug,
  env_slug
}: ServiceGitSourceFormProps) {
  const loaderData = useLoaderData<Route.ComponentProps["loaderData"]>();
  const { data: gitAppList } = useQuery({
    ...gitAppsQueries.list,
    initialData: loaderData.gitAppList
  });

  const { data: service } = useServiceQuery({
    project_slug,
    service_slug,
    env_slug
  });

  const serviceSourceChange = service.unapplied_changes.find(
    (change) => change.field === "git_source"
  ) as
    | {
        new_value: Pick<
          Service,
          "repository_url" | "branch_name" | "commit_sha" | "git_app"
        >;
        id: string;
      }
    | undefined;

  const { fetcher, data, reset } = useFetcherWithCallbacks({
    onSettled(data) {
      if (data.errors) {
        const errors = getFormErrorsFromResponseData(data?.errors);
        const key = Object.keys(errors.new_value ?? {})[0];

        const field = formRef.current?.elements.namedItem(
          key
        ) as HTMLInputElement;
        field?.focus();
      }
    },
    onSuccess(data) {
      setIsEditing(false);
      resetDefaultValues();
    }
  });
  const isPending = fetcher.state !== "idle";
  const [isEditing, setIsEditing] = React.useState(false);
  const SelectTriggerRef =
    React.useRef<React.ComponentRef<typeof SelectTrigger>>(null);

  const inputRef = React.useRef<React.ComponentRef<"input">>(null);
  const formRef = React.useRef<React.ComponentRef<"form">>(null);

  const serviceRepoURL =
    serviceSourceChange?.new_value.repository_url ?? service.repository_url!;
  const serviceBranch =
    serviceSourceChange?.new_value.branch_name ?? service.branch_name!;
  const serviceCommitSha =
    serviceSourceChange?.new_value.commit_sha ?? service.commit_sha!;

  const serviceRepo = service.next_git_repository ?? service.git_repository;
  const serviceGitApp = serviceSourceChange
    ? serviceSourceChange.new_value.git_app
    : service.git_app;

  const repoUrl = new URL(serviceRepoURL);
  const errors = getFormErrorsFromResponseData(data?.errors);

  const [selectedGitApp, setSelectedGitApp] = React.useState(serviceGitApp);
  const [selectedRepository, setSelectedRepository] = React.useState(
    service.next_git_repository ?? service.git_repository
  );
  const [repoSearchQuery, setRepoSearchQuery] = React.useState(
    selectedRepository?.path ?? ""
  );
  const [selectedBranch, setSelectedBranch] = React.useState(serviceBranch);
  const [branchSearchQuery, setBranchSearchQuery] =
    React.useState(selectedBranch);
  const [repositoryURL, setRepositoryURL] = React.useState(serviceRepoURL);

  const resetDefaultValues = () => {
    const serviceGitApp = serviceSourceChange
      ? serviceSourceChange.new_value.git_app
      : service.git_app;
    const serviceRepo = service.next_git_repository ?? service.git_repository;
    const serviceBranch =
      serviceSourceChange?.new_value.branch_name ?? service.branch_name!;

    setSelectedGitApp(serviceGitApp);
    setSelectedRepository(serviceRepo);
    setRepoSearchQuery(serviceRepo?.path ?? "");
    setSelectedBranch(serviceBranch);
    setBranchSearchQuery(serviceBranch);
  };

  return (
    <div className="w-full max-w-4xl">
      <fetcher.Form
        method="post"
        className="flex flex-col gap-4 w-full"
        ref={formRef}
      >
        <input type="hidden" name="change_field" value="git_source" />
        <input type="hidden" name="change_type" value="UPDATE" />
        <input type="hidden" name="change_id" value={serviceSourceChange?.id} />

        <div className="flex flex-col gap-2">
          <input
            type="hidden"
            name="git_app_id"
            value={selectedGitApp?.id ?? ""}
          />
          <FieldSet
            errors={errors.new_value?.git_app_id}
            name="git_app"
            className="flex flex-col gap-1.5 flex-1"
          >
            <FieldSetLabel htmlFor="git_app">Git app</FieldSetLabel>
            <FieldSetSelect
              name="git_app"
              data-edited={
                serviceSourceChange !== undefined ? "true" : undefined
              }
              disabled={!isEditing || serviceSourceChange !== undefined}
              value={selectedGitApp?.id ?? "none"}
              onValueChange={(id) =>
                setSelectedGitApp(
                  gitAppList.find((app) => app.id === id) ?? null
                )
              }
            >
              <SelectTrigger
                id="git_app"
                ref={SelectTriggerRef}
                data-edited={
                  serviceSourceChange !== undefined ? "true" : undefined
                }
                className={cn(
                  "disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
                  "data-[edited]:dark:disabled:bg-secondary-foreground",
                  "disabled:border-transparent disabled:opacity-100",
                  selectedGitApp === null &&
                    "disabled:font-mono disabled:text-grey"
                )}
              >
                <div className="flex items-center gap-2">
                  <SelectValue
                    className="flex items-center gap-2"
                    placeholder="Select a Git app"
                  />
                  {!selectedGitApp && (
                    <BanIcon className="opacity-50" size={15} />
                  )}
                  {selectedGitApp?.github && (
                    <GithubIcon className="opacity-50" size={15} />
                  )}
                  {selectedGitApp?.gitlab && (
                    <GitlabIcon className="opacity-50" size={15} />
                  )}
                </div>
              </SelectTrigger>
              <SelectContent>
                <SelectItem
                  value="none"
                  className="text-grey font-mono flex items-center gap-2"
                  rightIcon={BanIcon}
                >
                  {"<no app>"}
                </SelectItem>
                {gitAppList.map((gitapp) =>
                  gitapp.github ? (
                    <SelectItem
                      key={gitapp.id}
                      disabled={!gitapp.github.is_installed}
                      value={gitapp.id}
                      className="text-grey font-mono flex items-center gap-2"
                      rightIcon={GithubIcon}
                    >
                      {gitapp.github.name}
                    </SelectItem>
                  ) : gitapp.gitlab ? (
                    <SelectItem
                      key={gitapp.id}
                      value={gitapp.id}
                      className="text-grey font-mono flex items-center gap-2"
                      rightIcon={GitlabIcon}
                    >
                      {gitapp.gitlab.name}
                    </SelectItem>
                  ) : null
                )}
              </SelectContent>
            </FieldSetSelect>
          </FieldSet>
        </div>

        <FieldSet
          name="repository_url"
          className="flex flex-col gap-1.5 flex-1"
          required
          errors={errors.new_value?.repository_url}
        >
          <FieldSetLabel>Repository {!selectedGitApp && "URL"}</FieldSetLabel>
          <div className="relative">
            <FieldSetInput
              ref={inputRef}
              placeholder="ex: https://github.com/zane-ops/zane-ops"
              defaultValue={!!selectedGitApp ? undefined : serviceRepoURL}
              value={
                !!selectedGitApp
                  ? selectedRepository?.url ?? undefined
                  : undefined
              }
              readOnly={!!selectedGitApp}
              type={!!selectedGitApp ? "hidden" : "text"}
              data-edited={
                serviceSourceChange !== undefined ? "true" : undefined
              }
              disabled={!isEditing || serviceSourceChange !== undefined}
              onChange={(ev) => setRepositoryURL(ev.currentTarget.value)}
              className={cn(
                "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
                "data-[edited]:dark:disabled:bg-secondary-foreground",
                "disabled:border-transparent disabled:opacity-100",
                "disabled:text-transparent disabled:select-none"
              )}
            />
            {!isEditing && !selectedGitApp && (
              <span className="absolute inset-y-0 left-3 flex items-center pr-2 text-sm">
                <span className="text-grey">{repoUrl.origin}</span>
                <span>{repoUrl.pathname}</span>
              </span>
            )}
          </div>

          {selectedGitApp && (
            <GitRepositoryListInput
              appId={selectedGitApp.id}
              type={selectedGitApp.github ? "github" : "gitlab"}
              selectedRepository={selectedRepository}
              repoSearchQuery={repoSearchQuery}
              setRepoSearchQuery={setRepoSearchQuery}
              onSelect={setSelectedRepository}
              hasError={!!errors.new_value?.repository_url}
              disabled={!isEditing}
              edited={serviceSourceChange !== undefined}
            />
          )}
        </FieldSet>

        <div className="flex flex-col md:items-start gap-1.5 md:flex-row md:gap-3 w-full">
          <FieldSet
            name="branch_name"
            className="flex flex-col gap-1.5 flex-1"
            required
            errors={errors.new_value?.branch_name}
          >
            <FieldSetLabel>Branch name</FieldSetLabel>
            <div className="relative">
              <GitRepositoryBranchListInput
                repositoryURL={selectedRepository?.url ?? repositoryURL}
                appId={selectedGitApp?.id}
                selectedBranch={selectedBranch}
                searchQuery={branchSearchQuery}
                setSearchQuery={setBranchSearchQuery}
                onSelect={setSelectedBranch}
                hasError={!!errors.new_value?.branch_name}
                disabled={!isEditing}
                edited={serviceSourceChange !== undefined}
              />
            </div>
          </FieldSet>

          <FieldSet
            name="commit_sha"
            className="flex flex-col gap-1.5 flex-1"
            required
            errors={errors.new_value?.commit_sha}
          >
            <FieldSetLabel className="inline-flex items-center gap-0.5">
              Commit SHA&nbsp;
              <TooltipProvider>
                <Tooltip delayDuration={0}>
                  <TooltipTrigger>
                    <InfoIcon size={15} />
                  </TooltipTrigger>
                  <TooltipContent className="max-w-64">
                    <ul className="list-disc px-4 py-1">
                      <li>
                        You can use <Code>HEAD</Code> to reference the latest
                        commit of the branch
                      </li>
                      <li>
                        You can use either the short commit (7 chars minimum),
                        or the long commit sha
                      </li>
                    </ul>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </FieldSetLabel>
            <div className="relative">
              <FieldSetInput
                disabled={!isEditing || serviceSourceChange !== undefined}
                placeholder="ex: HEAD"
                defaultValue={serviceCommitSha}
                data-edited={
                  serviceSourceChange !== undefined ? "true" : undefined
                }
                className={cn(
                  "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
                  "data-[edited]:dark:disabled:bg-secondary-foreground",
                  "disabled:border-transparent disabled:opacity-100"
                )}
              />
            </div>
          </FieldSet>
        </div>
        <div className="flex gap-4">
          {serviceSourceChange !== undefined ? (
            <>
              <SubmitButton
                isPending={isPending}
                variant="outline"
                name="intent"
                value="cancel-service-change"
              >
                {isPending ? (
                  <>
                    <LoaderIcon className="animate-spin" size={15} />
                    <span>Discarding...</span>
                  </>
                ) : (
                  <>
                    <Undo2Icon size={15} className="flex-none" />
                    <span>Discard change</span>
                  </>
                )}
              </SubmitButton>
            </>
          ) : (
            <>
              {isEditing ? (
                <>
                  <SubmitButton
                    isPending={isPending}
                    variant="secondary"
                    className="self-start"
                    name="intent"
                    value="request-service-change"
                  >
                    {isPending ? (
                      <>
                        <LoaderIcon className="animate-spin" size={15} />
                        <span>Updating...</span>
                      </>
                    ) : (
                      <>
                        <CheckIcon size={15} className="flex-none" />
                        <span>Update</span>
                      </>
                    )}
                  </SubmitButton>
                  <Button
                    variant="outline"
                    type="reset"
                    disabled={isPending}
                    onClick={() => {
                      setIsEditing(false);
                      resetDefaultValues();
                      reset();
                    }}
                    className="bg-inherit inline-flex items-center gap-2 border-muted-foreground py-0.5"
                  >
                    <>
                      <XIcon size={15} className="flex-none" />
                      <span>Cancel</span>
                    </>
                  </Button>
                </>
              ) : (
                <Button
                  variant="outline"
                  type="button"
                  disabled={isPending}
                  onClick={() => {
                    flushSync(() => {
                      setIsEditing(true);
                    });
                    SelectTriggerRef.current?.focus();
                  }}
                  className="bg-inherit inline-flex items-center gap-2 border-muted-foreground py-0.5"
                >
                  <span>Edit</span>
                  <PencilLineIcon size={15} className="flex-none" />
                </Button>
              )}
            </>
          )}
        </div>
      </fetcher.Form>
    </div>
  );
}
