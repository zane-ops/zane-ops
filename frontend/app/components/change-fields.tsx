import Editor from "@monaco-editor/react";
import {
  ArrowDownIcon,
  ArrowRightIcon,
  FileSlidersIcon,
  GithubIcon,
  GitlabIcon,
  HardDriveIcon
} from "lucide-react";
import { Code } from "~/components/code";
import { Checkbox } from "~/components/ui/checkbox";
import { Input } from "~/components/ui/input";
import { BUILDER_DESCRIPTION_MAP } from "~/lib/constants";
import type { Service } from "~/lib/queries";
import { cn } from "~/lib/utils";

export type ChangeItemProps = {
  change: Service["unapplied_changes"][number];
  unapplied?: boolean;
};

export function VolumeChangeItem({
  change,
  unapplied = false
}: ChangeItemProps) {
  const new_value = change.new_value as Service["volumes"][number];
  const old_value = change.old_value as Service["volumes"][number];

  const getModeSuffix = (value: Service["volumes"][number]) => {
    return value.mode === "READ_ONLY" ? "read only" : "read & write";
  };

  return (
    <div className="flex flex-col md:flex-row gap-2 items-center overflow-x-auto">
      <div
        className={cn("rounded-md p-4 flex items-start gap-2 bg-muted w-full", {
          "dark:bg-primary-foreground bg-primary/60": change.type === "ADD",
          "dark:bg-red-500/20 bg-red-300/60": change.type === "DELETE"
        })}
      >
        <HardDriveIcon size={20} className="text-grey relative top-1.5" />
        <div className="flex flex-col gap-2">
          <h3 className="text-lg inline-flex gap-1 items-center">
            <span>{(old_value ?? new_value).name}</span>
            {change.type === "ADD" && (
              <span className="text-green-500">
                {unapplied && "will be"} added
              </span>
            )}
            {change.type === "DELETE" && (
              <span className="text-red-500">
                {unapplied && "will be"} removed
              </span>
            )}
          </h3>
          <small className="text-card-foreground inline-flex gap-1 items-center">
            {(old_value ?? new_value).host_path && (
              <>
                <span>{(old_value ?? new_value).host_path}</span>
                <ArrowRightIcon size={15} className="text-grey" />
              </>
            )}
            <span className="text-grey">
              {(old_value ?? new_value).container_path}
            </span>
            <Code>{getModeSuffix(old_value ?? new_value)}</Code>
          </small>
        </div>
      </div>

      {change.type === "UPDATE" && (
        <>
          <ArrowDownIcon
            size={24}
            className="text-grey md:-rotate-90 flex-none"
          />

          <div
            className={cn(
              "rounded-md p-4 flex items-start gap-2 bg-muted w-full",
              "dark:bg-secondary-foreground bg-secondary/60"
            )}
          >
            <HardDriveIcon size={20} className="text-grey relative top-1.5" />
            <div className="flex flex-col gap-2">
              <h3 className="text-lg inline-flex gap-1 items-center">
                <span>{new_value.name}</span>
                <span className="text-blue-500">
                  {unapplied && "will be"} updated
                </span>
              </h3>
              <small className="text-card-foreground inline-flex gap-1 items-center">
                {new_value.host_path && (
                  <>
                    <span>{new_value.host_path}</span>
                    <ArrowRightIcon size={15} className="text-grey" />
                  </>
                )}
                <span className="text-grey">{new_value.container_path}</span>
                <Code>{getModeSuffix(new_value)}</Code>
              </small>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export function SourceChangeField({
  change,
  unapplied = false
}: ChangeItemProps) {
  const new_value = change.new_value as Pick<Service, "image" | "credentials">;
  const old_value = change.old_value as Pick<Service, "image" | "credentials">;

  const getImageParts = (image: string) => {
    const serviceImage = image;
    const imageParts = serviceImage.split(":");
    const tag = imageParts.length > 1 ? imageParts.pop() : "latest";
    const docker_image = imageParts.join(":");
    return {
      image: docker_image,
      tag
    };
  };

  const oldImageParts = old_value?.image
    ? getImageParts(old_value.image)
    : null;
  const newImageParts = new_value?.image
    ? getImageParts(new_value.image)
    : null;

  return (
    <div className="flex flex-col md:flex-row gap-4 items-center overflow-x-auto">
      <div className="flex flex-col gap-4 w-full">
        <fieldset className="flex flex-col gap-1.5 flex-1">
          <label htmlFor="image">Source Image</label>
          <div className="relative">
            <Input
              id="image"
              name="image"
              disabled
              placeholder="<empty>"
              readOnly
              value={oldImageParts?.image}
              aria-labelledby="image-error"
              className={cn(
                "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
                "data-[edited]:dark:disabled:bg-secondary-foreground",
                "disabled:border-transparent disabled:opacity-100",
                "disabled:text-transparent"
              )}
            />
            {oldImageParts && (
              <span className="absolute inset-y-0 left-3 flex items-center pr-2 text-sm">
                {oldImageParts.image}
                <span className="text-grey">:{oldImageParts.tag}</span>
              </span>
            )}
          </div>
        </fieldset>

        <fieldset className="w-full flex flex-col gap-2">
          <legend>Credentials</legend>
          <label
            className="text-muted-foreground"
            htmlFor="credentials.username"
          >
            Username for registry
          </label>
          <div className="flex flex-col gap-1">
            <Input
              placeholder="<empty>"
              name="credentials.username"
              id="credentials.username"
              disabled
              defaultValue={old_value?.credentials?.username}
              className={cn(
                "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
                "data-[edited]:dark:disabled:bg-secondary-foreground",
                "disabled:border-transparent disabled:opacity-100 disabled:select-none"
              )}
            />
          </div>

          <label
            className="text-muted-foreground"
            htmlFor="credentials.password"
          >
            Password for registry
          </label>
          <div className="flex gap-2 items-start">
            <div className="inline-flex flex-col gap-1 flex-1">
              <Input
                placeholder="<empty>"
                disabled
                defaultValue={old_value?.credentials?.password}
                name="credentials.password"
                id="credentials.password"
                className={cn(
                  "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
                  "data-[edited]:dark:disabled:bg-secondary-foreground",
                  "disabled:border-transparent disabled:opacity-100"
                )}
              />
            </div>
          </div>
        </fieldset>
      </div>

      <ArrowDownIcon size={24} className="text-grey md:-rotate-90 flex-none" />

      <div className="flex flex-col gap-4 w-full">
        <fieldset className="flex flex-col gap-1.5 flex-1">
          <label htmlFor="image">
            Source Image&nbsp;
            <span className="text-blue-500">
              {unapplied && "will be"} updated
            </span>
          </label>
          <div className="relative">
            <Input
              id="image"
              name="image"
              disabled
              placeholder="<empty>"
              readOnly
              value={newImageParts?.image}
              aria-labelledby="image-error"
              className={cn(
                "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited=true]:disabled:bg-secondary/60",
                "data-[edited=true]:dark:disabled:bg-secondary-foreground",
                "disabled:border-transparent disabled:opacity-100",
                "disabled:text-transparent"
              )}
              data-edited
            />
            {newImageParts && (
              <span className="absolute inset-y-0 left-3 flex items-center pr-2 text-sm">
                {newImageParts.image}
                <span className="text-grey">:{newImageParts.tag}</span>
              </span>
            )}
          </div>
        </fieldset>

        <fieldset className="w-full flex flex-col gap-2">
          <legend>
            Credentials&nbsp;
            <span className="text-blue-500">
              {unapplied && "will be"} updated
            </span>
          </legend>
          <label
            className="text-muted-foreground"
            htmlFor="credentials.username"
          >
            Username for registry
          </label>
          <div className="flex flex-col gap-1">
            <Input
              placeholder="<empty>"
              id="credentials.username"
              disabled
              value={new_value?.credentials?.username}
              readOnly
              data-edited
              className={cn(
                "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited=true]:disabled:bg-secondary/60",
                "data-[edited=true]:dark:disabled:bg-secondary-foreground",
                "disabled:border-transparent disabled:opacity-100 disabled:select-none"
              )}
            />
          </div>

          <label
            className="text-muted-foreground"
            htmlFor="credentials.password"
          >
            Password for registry
          </label>
          <div className="flex gap-2 items-start">
            <div className="inline-flex flex-col gap-1 flex-1">
              <Input
                placeholder="<empty>"
                disabled
                id="credentials.password"
                value={new_value?.credentials?.password}
                readOnly
                data-edited
                className={cn(
                  "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited=true]:disabled:bg-secondary/60",
                  "data-[edited=true]:dark:disabled:bg-secondary-foreground",
                  "disabled:border-transparent disabled:opacity-100"
                )}
              />
            </div>
          </div>
        </fieldset>
      </div>
    </div>
  );
}

export function GitSourceChangeField({
  change,
  unapplied = false
}: ChangeItemProps) {
  const new_value = change.new_value as Pick<
    Service,
    "repository_url" | "branch_name" | "commit_sha" | "git_app"
  > | null;
  const old_value = change.old_value as Pick<
    Service,
    "repository_url" | "branch_name" | "commit_sha" | "git_app"
  > | null;

  const oldRepoUrl = old_value?.repository_url
    ? new URL(old_value.repository_url)
    : null;
  const newRepoUrl = new_value?.repository_url
    ? new URL(new_value.repository_url)
    : null;

  return (
    <div className="flex flex-col md:flex-row gap-4 items-center overflow-x-auto">
      <div className="flex flex-col gap-4 w-full">
        <fieldset className="flex flex-col gap-1.5 flex-1">
          <label htmlFor="old_git_app">Git app</label>
          <div className="relative">
            <Input
              disabled
              placeholder="<no app>"
              id="old_git_app"
              value={
                old_value?.git_app?.github?.name ??
                old_value?.git_app?.gitlab?.name
              }
              className={cn(
                "disabled:placeholder-shown:font-mono disabled:bg-muted ",
                "disabled:border-transparent disabled:opacity-100",
                "disabled:text-transparent"
              )}
            />
            <div className="absolute inset-0 flex items-center gap-2 px-2 font-mono">
              {old_value?.git_app?.github && (
                <>
                  <span>{old_value.git_app.github.name}</span>
                  <GithubIcon className="opacity-50" size={15} />
                </>
              )}
              {old_value?.git_app?.gitlab && (
                <>
                  <span>{old_value.git_app.gitlab.name}</span>
                  <GitlabIcon className="opacity-50" size={15} />
                </>
              )}
            </div>
          </div>
        </fieldset>
        <fieldset className="flex flex-col gap-1.5 flex-1">
          <label htmlFor="old_repository_url">Repository URL</label>
          <div className="relative">
            <Input
              disabled
              placeholder="<empty>"
              id="old_repository_url"
              value={old_value?.repository_url}
              className={cn(
                "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
                "data-[edited]:dark:disabled:bg-secondary-foreground",
                "disabled:border-transparent disabled:opacity-100",
                "disabled:text-transparent"
              )}
            />
            {oldRepoUrl && (
              <span className="absolute inset-0 left-3 flex items-center overflow-auto pr-4 text-sm">
                <span className="text-grey whitespace-nowrap">
                  {oldRepoUrl.origin}
                </span>
                <span className="whitespace-nowrap">{oldRepoUrl.pathname}</span>
              </span>
            )}
          </div>
        </fieldset>

        <div className="w-full flex flex-col gap-2">
          <label className="text-muted-foreground" htmlFor="old_branch_name">
            Branch name
          </label>
          <div className="flex flex-col gap-1">
            <Input
              placeholder="<empty>"
              id="old_branch_name"
              disabled
              defaultValue={old_value?.branch_name}
              className={cn(
                "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
                "data-[edited]:dark:disabled:bg-secondary-foreground",
                "disabled:border-transparent disabled:opacity-100 disabled:select-none"
              )}
            />
          </div>

          <label className="text-muted-foreground" htmlFor="old_commit_sha">
            Commit SHA
          </label>
          <div className="flex gap-2 items-start">
            <div className="inline-flex flex-col gap-1 flex-1">
              <Input
                placeholder="<empty>"
                disabled
                defaultValue={old_value?.commit_sha}
                id="old_commit_sha"
                className={cn(
                  "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
                  "data-[edited]:dark:disabled:bg-secondary-foreground",
                  "disabled:border-transparent disabled:opacity-100"
                )}
              />
            </div>
          </div>
        </div>
      </div>

      <ArrowDownIcon size={24} className="text-grey md:-rotate-90 flex-none" />

      <div className="flex flex-col gap-4 w-full">
        <fieldset className="flex flex-col gap-1.5 flex-1">
          <label htmlFor="new_git_app">Git app</label>
          <div className="relative">
            <Input
              disabled
              placeholder="<no app>"
              id="new_git_app"
              value={
                new_value?.git_app?.github?.name ??
                new_value?.git_app?.gitlab?.name
              }
              className={cn(
                "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited=true]:disabled:bg-secondary/60",
                "data-[edited=true]:dark:disabled:bg-secondary-foreground",
                "disabled:border-transparent disabled:opacity-100",
                "disabled:text-transparent"
              )}
              data-edited
            />
            <div className="absolute inset-0 flex items-center gap-2 px-2 font-mono">
              {new_value?.git_app?.github && (
                <>
                  <span>{new_value.git_app.github.name}</span>
                  <GithubIcon className="opacity-50" size={15} />
                </>
              )}
              {new_value?.git_app?.gitlab && (
                <>
                  <span>{new_value.git_app.gitlab.name}</span>
                  <GitlabIcon className="opacity-50" size={15} />
                </>
              )}
            </div>
          </div>
        </fieldset>
        <fieldset className="flex flex-col gap-1.5 flex-1">
          <label htmlFor="new_repository_url">
            Repository URL&nbsp;
            <span className="text-blue-500">
              {unapplied && "will be"} updated
            </span>
          </label>
          <div className="relative">
            <Input
              disabled
              placeholder="<empty>"
              id="new_repository_url"
              value={new_value?.repository_url}
              aria-labelledby="image-error"
              className={cn(
                "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited=true]:disabled:bg-secondary/60",
                "data-[edited=true]:dark:disabled:bg-secondary-foreground",
                "disabled:border-transparent disabled:opacity-100",
                "disabled:text-transparent"
              )}
              data-edited
            />
            {newRepoUrl && (
              <span className="absolute inset-0 left-3 flex items-center overflow-auto pr-4 text-sm">
                <span className="text-grey whitespace-nowrap">
                  {newRepoUrl.origin}
                </span>
                <span className="whitespace-nowrap">{newRepoUrl.pathname}</span>
              </span>
            )}
          </div>
        </fieldset>

        <div className="w-full flex flex-col gap-2">
          <label className="text-muted-foreground" htmlFor="new_branch_name">
            Branch name
          </label>
          <div className="flex flex-col gap-1">
            <Input
              placeholder="<empty>"
              id="new_branch_name"
              disabled
              value={new_value?.branch_name}
              readOnly
              data-edited
              className={cn(
                "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited=true]:disabled:bg-secondary/60",
                "data-[edited=true]:dark:disabled:bg-secondary-foreground",
                "disabled:border-transparent disabled:opacity-100 disabled:select-none"
              )}
            />
          </div>

          <label className="text-muted-foreground" htmlFor="new_commit_sha">
            Commit SHA
          </label>
          <div className="flex gap-2 items-start">
            <div className="inline-flex flex-col gap-1 flex-1">
              <Input
                placeholder="<empty>"
                disabled
                id="new_commit_sha"
                value={new_value?.commit_sha}
                readOnly
                data-edited
                className={cn(
                  "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited=true]:disabled:bg-secondary/60",
                  "data-[edited=true]:dark:disabled:bg-secondary-foreground",
                  "disabled:border-transparent disabled:opacity-100"
                )}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

type ServiceBuilder = Exclude<NonNullable<Service["builder"]>, "">;
type ServiceBuilderChangeNewValue = {
  builder: ServiceBuilder;
  options: Service["dockerfile_builder_options"] &
    Service["static_dir_builder_options"] &
    Service["nixpacks_builder_options"] &
    Service["railpack_builder_options"];
};

export function BuilderChangeField({
  change,
  unapplied = false
}: ChangeItemProps) {
  const new_value = change.new_value as ServiceBuilderChangeNewValue | null;
  const old_value = change.old_value as ServiceBuilderChangeNewValue | null;

  const oldBuilder = old_value?.builder;
  const newBuilder = new_value?.builder;

  return (
    <div className="flex flex-col md:flex-row gap-4 items-center overflow-x-auto">
      <div className="flex flex-col gap-4 w-full">
        <div
          className={cn(
            "w-full px-3 bg-muted rounded-md flex flex-col gap-2 items-start text-start flex-wrap pr-24 py-4",
            "text-base"
          )}
        >
          <div className="flex flex-col gap-2 items-start">
            <div className="inline-flex gap-2 items-center flex-wrap">
              {!oldBuilder ? (
                <p className="text-grey font-mono">{`<empty>`}</p>
              ) : (
                <p>{BUILDER_DESCRIPTION_MAP[oldBuilder].title}</p>
              )}
            </div>

            <small className="inline-flex gap-2 items-center">
              <span className="text-grey">
                {!oldBuilder ? (
                  <>empty</>
                ) : (
                  BUILDER_DESCRIPTION_MAP[oldBuilder].description
                )}
              </span>
            </small>
          </div>
        </div>

        {oldBuilder === "DOCKERFILE" && (
          <>
            <fieldset className="flex flex-col gap-1.5 flex-1">
              <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Build context directory
              </label>
              <div className="relative">
                <Input
                  disabled
                  placeholder="<empty>"
                  defaultValue={old_value?.options?.build_context_dir}
                  className={cn(
                    "disabled:bg-muted",
                    "disabled:border-transparent disabled:opacity-100",
                    "disabled:placeholder-shown:font-mono"
                  )}
                />
              </div>
            </fieldset>

            <fieldset
              name="dockerfile_path"
              className="flex flex-col gap-1.5 flex-1"
            >
              <label className="dark:text-card-foreground  inline-flex items-center gap-0.5">
                Dockerfile location
              </label>
              <div className="relative">
                <Input
                  disabled
                  placeholder="<empty>"
                  defaultValue={old_value?.options?.dockerfile_path}
                  className={cn(
                    "disabled:bg-muted",
                    "disabled:border-transparent disabled:opacity-100",
                    "disabled:placeholder-shown:font-mono"
                  )}
                />
              </div>
            </fieldset>

            <fieldset
              name="build_stage_target"
              className="flex flex-col gap-1.5 flex-1"
            >
              <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Docker build stage target
              </label>
              <div className="relative">
                <Input
                  disabled
                  placeholder="<empty>"
                  defaultValue={old_value?.options?.build_stage_target}
                  className={cn(
                    "disabled:bg-muted",
                    "disabled:placeholder-shown:font-mono",
                    "disabled:border-transparent disabled:opacity-100"
                  )}
                />
              </div>
            </fieldset>
          </>
        )}

        {oldBuilder === "STATIC_DIR" && (
          <>
            <fieldset className="flex flex-col gap-1.5 flex-1">
              <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Publish directory
              </label>
              <div className="relative">
                <Input
                  disabled
                  placeholder="<empty>"
                  defaultValue={old_value?.options?.publish_directory}
                  className={cn(
                    "disabled:bg-muted",
                    "disabled:border-transparent disabled:opacity-100",
                    "disabled:placeholder-shown:font-mono"
                  )}
                />
              </div>
            </fieldset>

            {!old_value?.options?.is_spa && (
              <fieldset className="flex flex-col gap-1.5 flex-1">
                <label className="dark:text-card-foreground  inline-flex items-center gap-0.5">
                  Not found page
                </label>
                <div className="relative">
                  <Input
                    disabled
                    placeholder="<empty>"
                    defaultValue={old_value?.options?.not_found_page}
                    className={cn(
                      "disabled:bg-muted",
                      "disabled:border-transparent disabled:opacity-100",
                      "disabled:placeholder-shown:font-mono"
                    )}
                  />
                </div>
              </fieldset>
            )}

            <fieldset className="flex-1 inline-flex gap-2 flex-col">
              <div className="inline-flex gap-2 items-center">
                <Checkbox
                  defaultChecked={old_value?.options?.is_spa}
                  disabled
                />

                <label className="inline-flex gap-1 items-center text-grey">
                  Is this a Single Page Application (SPA) ?
                </label>
              </div>
            </fieldset>
            {old_value?.options?.is_spa && (
              <fieldset className="flex flex-col gap-1.5 flex-1">
                <label className="dark:text-card-foreground  inline-flex items-center gap-0.5">
                  Index page
                </label>
                <div className="relative">
                  <Input
                    disabled
                    placeholder="<empty>"
                    defaultValue={old_value?.options?.index_page}
                    className={cn(
                      "disabled:bg-muted",
                      "disabled:border-transparent disabled:opacity-100",
                      "disabled:placeholder-shown:font-mono"
                    )}
                  />
                </div>
              </fieldset>
            )}
            <label>Generated Caddyfile</label>
            <div
              className={cn(
                "resize-y h-52 min-h-52 overflow-y-auto overflow-x-clip max-w-full",
                "w-[85dvw] sm:w-[90dvw] md:w-[380px]"
              )}
            >
              <Editor
                className="w-full h-full max-w-full"
                value={old_value?.options?.generated_caddyfile ?? ""}
                theme="vs-dark"
                options={{
                  readOnly: true,
                  minimap: {
                    enabled: false
                  }
                }}
              />
            </div>
          </>
        )}

        {oldBuilder === "NIXPACKS" && (
          <>
            <fieldset className="flex flex-col gap-1.5 flex-1">
              <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Build directory
              </label>
              <div className="relative">
                <Input
                  disabled
                  placeholder="<empty>"
                  defaultValue={old_value?.options?.build_directory}
                  className={cn(
                    "disabled:bg-muted",
                    "disabled:border-transparent disabled:opacity-100",
                    "disabled:placeholder-shown:font-mono"
                  )}
                />
              </div>
            </fieldset>
            <fieldset className="flex flex-col gap-1.5 flex-1">
              <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Custom install command
              </label>
              <div className="relative">
                <Input
                  disabled
                  placeholder="<empty>"
                  defaultValue={old_value?.options?.custom_install_command}
                  className={cn(
                    "disabled:bg-muted",
                    "disabled:border-transparent disabled:opacity-100",
                    "disabled:placeholder-shown:font-mono"
                  )}
                />
              </div>
            </fieldset>
            <fieldset className="flex flex-col gap-1.5 flex-1">
              <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Custom build command
              </label>
              <div className="relative">
                <Input
                  disabled
                  placeholder="<empty>"
                  defaultValue={old_value?.options?.custom_build_command}
                  className={cn(
                    "disabled:bg-muted",
                    "disabled:border-transparent disabled:opacity-100",
                    "disabled:placeholder-shown:font-mono"
                  )}
                />
              </div>
            </fieldset>

            {!old_value?.options?.is_static && (
              <fieldset className="flex flex-col gap-1.5 flex-1">
                <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                  Custom start command
                </label>
                <div className="relative">
                  <Input
                    disabled
                    placeholder="<empty>"
                    defaultValue={old_value?.options?.custom_start_command}
                    className={cn(
                      "disabled:bg-muted",
                      "disabled:border-transparent disabled:opacity-100",
                      "disabled:placeholder-shown:font-mono"
                    )}
                  />
                </div>
              </fieldset>
            )}
            <fieldset className="flex-1 inline-flex gap-2 flex-col">
              <div className="inline-flex gap-2 items-start">
                <Checkbox
                  defaultChecked={old_value?.options?.is_static}
                  disabled
                  className="relative top-1"
                />

                <label className="inline-flex items-start flex-col">
                  <span>Is this a Static website ?</span>
                </label>
              </div>
            </fieldset>
            {old_value?.options?.is_static && (
              <>
                <fieldset className="flex-1 inline-flex gap-2 flex-col">
                  <div className="inline-flex gap-2 items-start">
                    <Checkbox
                      defaultChecked={old_value?.options?.is_spa}
                      disabled
                      className="relative top-1"
                    />

                    <label className="inline-flex items-start flex-col">
                      <span>Is this a Single Page Application (SPA) ?</span>
                    </label>
                  </div>
                </fieldset>
                <fieldset className="flex flex-col gap-1.5 flex-1">
                  <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                    Publish directory
                  </label>
                  <div className="relative">
                    <Input
                      disabled
                      placeholder="<empty>"
                      defaultValue={old_value?.options?.publish_directory}
                      className={cn(
                        "disabled:bg-muted",
                        "disabled:border-transparent disabled:opacity-100",
                        "disabled:placeholder-shown:font-mono"
                      )}
                    />
                  </div>
                </fieldset>

                {old_value?.options?.is_spa ? (
                  <fieldset className="flex flex-col gap-1.5 flex-1">
                    <label className="dark:text-card-foreground  inline-flex items-center gap-0.5">
                      Index page
                    </label>
                    <div className="relative">
                      <Input
                        disabled
                        placeholder="<empty>"
                        defaultValue={old_value?.options?.index_page}
                        className={cn(
                          "disabled:bg-muted",
                          "disabled:border-transparent disabled:opacity-100",
                          "disabled:placeholder-shown:font-mono"
                        )}
                      />
                    </div>
                  </fieldset>
                ) : (
                  <fieldset className="flex flex-col gap-1.5 flex-1">
                    <label className="dark:text-card-foreground  inline-flex items-center gap-0.5">
                      Not found page
                    </label>
                    <div className="relative">
                      <Input
                        disabled
                        placeholder="<empty>"
                        defaultValue={old_value?.options?.not_found_page}
                        className={cn(
                          "disabled:bg-muted",
                          "disabled:border-transparent disabled:opacity-100",
                          "disabled:placeholder-shown:font-mono"
                        )}
                      />
                    </div>
                  </fieldset>
                )}

                <label>Generated Caddyfile&nbsp;</label>
                <div
                  className={cn(
                    "resize-y h-52 min-h-52 overflow-y-auto overflow-x-clip max-w-full",
                    "w-[85dvw] sm:w-[90dvw] md:w-[380px]"
                  )}
                >
                  <Editor
                    className="w-full h-full max-w-full"
                    value={old_value?.options?.generated_caddyfile ?? ""}
                    theme="vs-dark"
                    language="ini"
                    options={{
                      readOnly: true,
                      minimap: {
                        enabled: false
                      }
                    }}
                  />
                </div>
              </>
            )}
          </>
        )}

        {oldBuilder === "RAILPACK" && (
          <>
            <fieldset className="flex flex-col gap-1.5 flex-1">
              <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Build directory
              </label>
              <div className="relative">
                <Input
                  disabled
                  placeholder="<empty>"
                  defaultValue={old_value?.options?.build_directory}
                  className={cn(
                    "disabled:bg-muted",
                    "disabled:border-transparent disabled:opacity-100",
                    "disabled:placeholder-shown:font-mono"
                  )}
                />
              </div>
            </fieldset>
            <fieldset className="flex flex-col gap-1.5 flex-1">
              <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Custom install command
              </label>
              <div className="relative">
                <Input
                  disabled
                  placeholder="<empty>"
                  defaultValue={old_value?.options?.custom_install_command}
                  className={cn(
                    "disabled:bg-muted",
                    "disabled:border-transparent disabled:opacity-100",
                    "disabled:placeholder-shown:font-mono"
                  )}
                />
              </div>
            </fieldset>
            <fieldset className="flex flex-col gap-1.5 flex-1">
              <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Custom build command
              </label>
              <div className="relative">
                <Input
                  disabled
                  placeholder="<empty>"
                  defaultValue={old_value?.options?.custom_build_command}
                  className={cn(
                    "disabled:bg-muted",
                    "disabled:border-transparent disabled:opacity-100",
                    "disabled:placeholder-shown:font-mono"
                  )}
                />
              </div>
            </fieldset>

            {!old_value?.options?.is_static && (
              <fieldset className="flex flex-col gap-1.5 flex-1">
                <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                  Custom start command
                </label>
                <div className="relative">
                  <Input
                    disabled
                    placeholder="<empty>"
                    defaultValue={old_value?.options?.custom_start_command}
                    className={cn(
                      "disabled:bg-muted",
                      "disabled:border-transparent disabled:opacity-100",
                      "disabled:placeholder-shown:font-mono"
                    )}
                  />
                </div>
              </fieldset>
            )}
            <fieldset className="flex-1 inline-flex gap-2 flex-col">
              <div className="inline-flex gap-2 items-start">
                <Checkbox
                  defaultChecked={old_value?.options?.is_static}
                  disabled
                  className="relative top-1"
                />

                <label className="inline-flex items-start flex-col">
                  <span>Is this a Static website ?</span>
                </label>
              </div>
            </fieldset>
            {old_value?.options?.is_static && (
              <>
                <fieldset className="flex-1 inline-flex gap-2 flex-col">
                  <div className="inline-flex gap-2 items-start">
                    <Checkbox
                      defaultChecked={old_value?.options?.is_spa}
                      disabled
                      className="relative top-1"
                    />

                    <label className="inline-flex items-start flex-col">
                      <span>Is this a Single Page Application (SPA) ?</span>
                    </label>
                  </div>
                </fieldset>
                <fieldset className="flex flex-col gap-1.5 flex-1">
                  <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                    Publish directory
                  </label>
                  <div className="relative">
                    <Input
                      disabled
                      placeholder="<empty>"
                      defaultValue={old_value?.options?.publish_directory}
                      className={cn(
                        "disabled:bg-muted",
                        "disabled:border-transparent disabled:opacity-100",
                        "disabled:placeholder-shown:font-mono"
                      )}
                    />
                  </div>
                </fieldset>

                {old_value?.options?.is_spa ? (
                  <fieldset className="flex flex-col gap-1.5 flex-1">
                    <label className="dark:text-card-foreground  inline-flex items-center gap-0.5">
                      Index page
                    </label>
                    <div className="relative">
                      <Input
                        disabled
                        placeholder="<empty>"
                        defaultValue={old_value?.options?.index_page}
                        className={cn(
                          "disabled:bg-muted",
                          "disabled:border-transparent disabled:opacity-100",
                          "disabled:placeholder-shown:font-mono"
                        )}
                      />
                    </div>
                  </fieldset>
                ) : (
                  <fieldset className="flex flex-col gap-1.5 flex-1">
                    <label className="dark:text-card-foreground  inline-flex items-center gap-0.5">
                      Not found page
                    </label>
                    <div className="relative">
                      <Input
                        disabled
                        placeholder="<empty>"
                        defaultValue={old_value?.options?.not_found_page}
                        className={cn(
                          "disabled:bg-muted",
                          "disabled:border-transparent disabled:opacity-100",
                          "disabled:placeholder-shown:font-mono"
                        )}
                      />
                    </div>
                  </fieldset>
                )}

                <label>Generated Caddyfile&nbsp;</label>
                <div
                  className={cn(
                    "resize-y h-52 min-h-52 overflow-y-auto overflow-x-clip max-w-full",
                    "w-[85dvw] sm:w-[90dvw] md:w-[380px]"
                  )}
                >
                  <Editor
                    className="w-full h-full max-w-full"
                    value={old_value?.options?.generated_caddyfile ?? ""}
                    theme="vs-dark"
                    language="ini"
                    options={{
                      readOnly: true,
                      minimap: {
                        enabled: false
                      }
                    }}
                  />
                </div>
              </>
            )}
          </>
        )}
      </div>

      <ArrowDownIcon size={24} className="text-grey md:-rotate-90 flex-none" />

      <div className="flex flex-col gap-4 w-full">
        <div
          className={cn(
            "w-full px-3 bg-muted rounded-md flex flex-col gap-2 items-start text-start flex-wrap pr-24 py-4",
            "text-base",
            "dark:bg-secondary-foreground bg-secondary/60"
          )}
        >
          <div className="flex flex-col gap-2 items-start">
            <div className="inline-flex gap-2 items-center flex-wrap">
              {!newBuilder ? (
                <p className="text-grey font-mono">{`<empty>`}</p>
              ) : (
                <p>{BUILDER_DESCRIPTION_MAP[newBuilder].title}</p>
              )}
              <span className="text-blue-500">
                {unapplied && "will be"} updated
              </span>
            </div>

            <small className="inline-flex gap-2 items-center">
              <span className="text-grey">
                {!newBuilder ? (
                  <>empty</>
                ) : (
                  BUILDER_DESCRIPTION_MAP[newBuilder].description
                )}
              </span>
            </small>
          </div>
        </div>

        {newBuilder === "DOCKERFILE" && (
          <>
            <fieldset className="flex flex-col gap-1.5 flex-1">
              <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Build context directory&nbsp;
                <span className="text-blue-500">
                  {unapplied && "will be"} updated
                </span>
              </label>
              <div className="relative">
                <Input
                  disabled
                  placeholder="<empty>"
                  defaultValue={new_value?.options?.build_context_dir}
                  className={cn(
                    "disabled:bg-secondary/60",
                    "dark:disabled:bg-secondary-foreground",
                    "disabled:border-transparent disabled:opacity-100",
                    "disabled:placeholder-shown:font-mono"
                  )}
                />
              </div>
            </fieldset>

            <fieldset
              name="dockerfile_path"
              className="flex flex-col gap-1.5 flex-1"
            >
              <label className="dark:text-card-foreground  inline-flex items-center gap-0.5">
                Dockerfile location&nbsp;
                <span className="text-blue-500">
                  {unapplied && "will be"} updated
                </span>
              </label>
              <div className="relative">
                <Input
                  disabled
                  placeholder="<empty>"
                  defaultValue={new_value?.options?.dockerfile_path}
                  className={cn(
                    "disabled:bg-secondary/60",
                    "dark:disabled:bg-secondary-foreground",
                    "disabled:border-transparent disabled:opacity-100",
                    "disabled:placeholder-shown:font-mono"
                  )}
                />
              </div>
            </fieldset>

            <fieldset
              name="build_stage_target"
              className="flex flex-col gap-1.5 flex-1"
            >
              <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Docker build stage target&nbsp;
                <span className="text-blue-500">
                  {unapplied && "will be"} updated
                </span>
              </label>
              <div className="relative">
                <Input
                  disabled
                  placeholder="<empty>"
                  defaultValue={new_value?.options?.build_stage_target}
                  className={cn(
                    "disabled:placeholder-shown:font-mono disabled:bg-secondary/60",
                    "dark:disabled:bg-secondary-foreground",
                    "disabled:border-transparent disabled:opacity-100"
                  )}
                />
              </div>
            </fieldset>
          </>
        )}

        {newBuilder === "STATIC_DIR" && (
          <>
            <fieldset className="flex flex-col gap-1.5 flex-1">
              <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Publish directory
                <span className="text-blue-500">
                  {unapplied && "will be"} updated
                </span>
              </label>
              <div className="relative">
                <Input
                  disabled
                  placeholder="<empty>"
                  defaultValue={new_value?.options?.publish_directory}
                  className={cn(
                    "disabled:bg-secondary/60",
                    "dark:disabled:bg-secondary-foreground",
                    "disabled:border-transparent disabled:opacity-100",
                    "disabled:placeholder-shown:font-mono"
                  )}
                />
              </div>
            </fieldset>

            {!new_value?.options?.is_spa && (
              <fieldset className="flex flex-col gap-1.5 flex-1">
                <label className="dark:text-card-foreground  inline-flex items-center gap-0.5">
                  Not found page
                  <span className="text-blue-500">
                    {unapplied && "will be"} updated
                  </span>
                </label>
                <div className="relative">
                  <Input
                    disabled
                    placeholder="<empty>"
                    defaultValue={new_value?.options?.not_found_page}
                    className={cn(
                      "disabled:bg-secondary/60",
                      "dark:disabled:bg-secondary-foreground",
                      "disabled:border-transparent disabled:opacity-100",
                      "disabled:placeholder-shown:font-mono"
                    )}
                  />
                </div>
              </fieldset>
            )}

            <fieldset className="flex-1 inline-flex gap-2 flex-col">
              <div className="inline-flex gap-2 items-start">
                <Checkbox
                  defaultChecked={new_value?.options?.is_spa}
                  disabled
                  className="relative top-1"
                />

                <label className="inline-flex items-start flex-col">
                  <span>Is this a Single Page Application (SPA) ?</span>
                  <span className="text-blue-500">
                    {unapplied && "will be"} updated
                  </span>
                </label>
              </div>
            </fieldset>
            {new_value?.options?.is_spa && (
              <fieldset className="flex flex-col gap-1.5 flex-1">
                <label className="dark:text-card-foreground  inline-flex items-center gap-0.5">
                  Index page
                  <span className="text-blue-500">
                    {unapplied && "will be"} updated
                  </span>
                </label>
                <div className="relative">
                  <Input
                    disabled
                    placeholder="<empty>"
                    defaultValue={new_value?.options?.index_page}
                    className={cn(
                      "disabled:bg-secondary/60",
                      "dark:disabled:bg-secondary-foreground",
                      "disabled:border-transparent disabled:opacity-100",
                      "disabled:placeholder-shown:font-mono"
                    )}
                  />
                </div>
              </fieldset>
            )}

            <label>
              Generated Caddyfile&nbsp;
              <span className="text-blue-500">
                {unapplied && "will be"} updated
              </span>
            </label>
            <div
              className={cn(
                "resize-y h-52 min-h-52 overflow-y-auto overflow-x-clip max-w-full",
                "w-[85dvw] sm:w-[90dvw] md:w-[380px]"
              )}
            >
              <Editor
                className="w-full h-full max-w-full"
                value={new_value?.options?.generated_caddyfile ?? ""}
                theme="vs-dark"
                language="ini"
                options={{
                  readOnly: true,
                  minimap: {
                    enabled: false
                  }
                }}
              />
            </div>
          </>
        )}

        {newBuilder === "NIXPACKS" && (
          <>
            <fieldset className="flex flex-col gap-1.5 flex-1">
              <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Build directory
                <span className="text-blue-500">
                  {unapplied && "will be"} updated
                </span>
              </label>
              <div className="relative">
                <Input
                  disabled
                  placeholder="<empty>"
                  defaultValue={new_value?.options?.build_directory}
                  className={cn(
                    "disabled:bg-secondary/60",
                    "dark:disabled:bg-secondary-foreground",
                    "disabled:border-transparent disabled:opacity-100",
                    "disabled:placeholder-shown:font-mono"
                  )}
                />
              </div>
            </fieldset>
            <fieldset className="flex flex-col gap-1.5 flex-1">
              <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Custom install command
                <span className="text-blue-500">
                  {unapplied && "will be"} updated
                </span>
              </label>
              <div className="relative">
                <Input
                  disabled
                  placeholder="<empty>"
                  defaultValue={new_value?.options?.custom_install_command}
                  className={cn(
                    "disabled:bg-secondary/60",
                    "dark:disabled:bg-secondary-foreground",
                    "disabled:border-transparent disabled:opacity-100",
                    "disabled:placeholder-shown:font-mono"
                  )}
                />
              </div>
            </fieldset>
            <fieldset className="flex flex-col gap-1.5 flex-1">
              <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Custom build command
                <span className="text-blue-500">
                  {unapplied && "will be"} updated
                </span>
              </label>
              <div className="relative">
                <Input
                  disabled
                  placeholder="<empty>"
                  defaultValue={new_value?.options?.custom_build_command}
                  className={cn(
                    "disabled:bg-secondary/60",
                    "dark:disabled:bg-secondary-foreground",
                    "disabled:border-transparent disabled:opacity-100",
                    "disabled:placeholder-shown:font-mono"
                  )}
                />
              </div>
            </fieldset>

            {!new_value?.options?.is_static && (
              <fieldset className="flex flex-col gap-1.5 flex-1">
                <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                  Custom start command
                  <span className="text-blue-500">
                    {unapplied && "will be"} updated
                  </span>
                </label>
                <div className="relative">
                  <Input
                    disabled
                    placeholder="<empty>"
                    defaultValue={new_value?.options?.custom_start_command}
                    className={cn(
                      "disabled:bg-secondary/60",
                      "dark:disabled:bg-secondary-foreground",
                      "disabled:border-transparent disabled:opacity-100",
                      "disabled:placeholder-shown:font-mono"
                    )}
                  />
                </div>
              </fieldset>
            )}
            <fieldset className="flex-1 inline-flex gap-2 flex-col">
              <div className="inline-flex gap-2 items-start">
                <Checkbox
                  defaultChecked={new_value?.options?.is_static}
                  disabled
                  className="relative top-1"
                />

                <label className="inline-flex items-start flex-col">
                  <span>Is this a Static website ?</span>
                  <span className="text-blue-500">
                    {unapplied && "will be"} updated
                  </span>
                </label>
              </div>
            </fieldset>
            {new_value?.options?.is_static && (
              <>
                <fieldset className="flex-1 inline-flex gap-2 flex-col">
                  <div className="inline-flex gap-2 items-start">
                    <Checkbox
                      defaultChecked={new_value?.options?.is_spa}
                      disabled
                      className="relative top-1"
                    />

                    <label className="inline-flex items-start flex-col">
                      <span>Is this a Single Page Application (SPA) ?</span>
                      <span className="text-blue-500">
                        {unapplied && "will be"} updated
                      </span>
                    </label>
                  </div>
                </fieldset>
                <fieldset className="flex flex-col gap-1.5 flex-1">
                  <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                    Publish directory
                    <span className="text-blue-500">
                      {unapplied && "will be"} updated
                    </span>
                  </label>
                  <div className="relative">
                    <Input
                      disabled
                      placeholder="<empty>"
                      defaultValue={new_value?.options?.publish_directory}
                      className={cn(
                        "disabled:bg-secondary/60",
                        "dark:disabled:bg-secondary-foreground",
                        "disabled:border-transparent disabled:opacity-100",
                        "disabled:placeholder-shown:font-mono"
                      )}
                    />
                  </div>
                </fieldset>

                {new_value?.options?.is_spa ? (
                  <fieldset className="flex flex-col gap-1.5 flex-1">
                    <label className="dark:text-card-foreground  inline-flex items-center gap-0.5">
                      Index page
                      <span className="text-blue-500">
                        {unapplied && "will be"} updated
                      </span>
                    </label>
                    <div className="relative">
                      <Input
                        disabled
                        placeholder="<empty>"
                        defaultValue={new_value?.options?.index_page}
                        className={cn(
                          "disabled:bg-secondary/60",
                          "dark:disabled:bg-secondary-foreground",
                          "disabled:border-transparent disabled:opacity-100",
                          "disabled:placeholder-shown:font-mono"
                        )}
                      />
                    </div>
                  </fieldset>
                ) : (
                  <fieldset className="flex flex-col gap-1.5 flex-1">
                    <label className="dark:text-card-foreground  inline-flex items-center gap-0.5">
                      Not found page
                      <span className="text-blue-500">
                        {unapplied && "will be"} updated
                      </span>
                    </label>
                    <div className="relative">
                      <Input
                        disabled
                        placeholder="<empty>"
                        defaultValue={new_value?.options?.not_found_page}
                        className={cn(
                          "disabled:bg-secondary/60",
                          "dark:disabled:bg-secondary-foreground",
                          "disabled:border-transparent disabled:opacity-100",
                          "disabled:placeholder-shown:font-mono"
                        )}
                      />
                    </div>
                  </fieldset>
                )}

                <label>
                  Generated Caddyfile&nbsp;
                  <span className="text-blue-500">
                    {unapplied && "will be"} updated
                  </span>
                </label>
                <div
                  className={cn(
                    "resize-y h-52 min-h-52 overflow-y-auto overflow-x-clip max-w-full",
                    "w-[85dvw] sm:w-[90dvw] md:w-[380px]"
                  )}
                >
                  <Editor
                    className="w-full h-full max-w-full"
                    value={new_value?.options?.generated_caddyfile ?? ""}
                    theme="vs-dark"
                    language="ini"
                    options={{
                      readOnly: true,
                      minimap: {
                        enabled: false
                      }
                    }}
                  />
                </div>
              </>
            )}
          </>
        )}

        {newBuilder === "RAILPACK" && (
          <>
            <fieldset className="flex flex-col gap-1.5 flex-1">
              <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Build directory
                <span className="text-blue-500">
                  {unapplied && "will be"} updated
                </span>
              </label>
              <div className="relative">
                <Input
                  disabled
                  placeholder="<empty>"
                  defaultValue={new_value?.options?.build_directory}
                  className={cn(
                    "disabled:bg-secondary/60",
                    "dark:disabled:bg-secondary-foreground",
                    "disabled:border-transparent disabled:opacity-100",
                    "disabled:placeholder-shown:font-mono"
                  )}
                />
              </div>
            </fieldset>
            <fieldset className="flex flex-col gap-1.5 flex-1">
              <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Custom install command
                <span className="text-blue-500">
                  {unapplied && "will be"} updated
                </span>
              </label>
              <div className="relative">
                <Input
                  disabled
                  placeholder="<empty>"
                  defaultValue={new_value?.options?.custom_install_command}
                  className={cn(
                    "disabled:bg-secondary/60",
                    "dark:disabled:bg-secondary-foreground",
                    "disabled:border-transparent disabled:opacity-100",
                    "disabled:placeholder-shown:font-mono"
                  )}
                />
              </div>
            </fieldset>
            <fieldset className="flex flex-col gap-1.5 flex-1">
              <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Custom build command
                <span className="text-blue-500">
                  {unapplied && "will be"} updated
                </span>
              </label>
              <div className="relative">
                <Input
                  disabled
                  placeholder="<empty>"
                  defaultValue={new_value?.options?.custom_build_command}
                  className={cn(
                    "disabled:bg-secondary/60",
                    "dark:disabled:bg-secondary-foreground",
                    "disabled:border-transparent disabled:opacity-100",
                    "disabled:placeholder-shown:font-mono"
                  )}
                />
              </div>
            </fieldset>

            {!new_value?.options?.is_static && (
              <fieldset className="flex flex-col gap-1.5 flex-1">
                <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                  Custom start command
                  <span className="text-blue-500">
                    {unapplied && "will be"} updated
                  </span>
                </label>
                <div className="relative">
                  <Input
                    disabled
                    placeholder="<empty>"
                    defaultValue={new_value?.options?.custom_start_command}
                    className={cn(
                      "disabled:bg-secondary/60",
                      "dark:disabled:bg-secondary-foreground",
                      "disabled:border-transparent disabled:opacity-100",
                      "disabled:placeholder-shown:font-mono"
                    )}
                  />
                </div>
              </fieldset>
            )}
            <fieldset className="flex-1 inline-flex gap-2 flex-col">
              <div className="inline-flex gap-2 items-start">
                <Checkbox
                  defaultChecked={new_value?.options?.is_static}
                  disabled
                  className="relative top-1"
                />

                <label className="inline-flex items-start flex-col">
                  <span>Is this a Static website ?</span>
                  <span className="text-blue-500">
                    {unapplied && "will be"} updated
                  </span>
                </label>
              </div>
            </fieldset>
            {new_value?.options?.is_static && (
              <>
                <fieldset className="flex-1 inline-flex gap-2 flex-col">
                  <div className="inline-flex gap-2 items-start">
                    <Checkbox
                      defaultChecked={new_value?.options?.is_spa}
                      disabled
                      className="relative top-1"
                    />

                    <label className="inline-flex items-start flex-col">
                      <span>Is this a Single Page Application (SPA) ?</span>
                      <span className="text-blue-500">
                        {unapplied && "will be"} updated
                      </span>
                    </label>
                  </div>
                </fieldset>
                <fieldset className="flex flex-col gap-1.5 flex-1">
                  <label className="dark:text-card-foreground inline-flex items-center gap-0.5">
                    Publish directory
                    <span className="text-blue-500">
                      {unapplied && "will be"} updated
                    </span>
                  </label>
                  <div className="relative">
                    <Input
                      disabled
                      placeholder="<empty>"
                      defaultValue={new_value?.options?.publish_directory}
                      className={cn(
                        "disabled:bg-secondary/60",
                        "dark:disabled:bg-secondary-foreground",
                        "disabled:border-transparent disabled:opacity-100",
                        "disabled:placeholder-shown:font-mono"
                      )}
                    />
                  </div>
                </fieldset>

                {new_value?.options?.is_spa ? (
                  <fieldset className="flex flex-col gap-1.5 flex-1">
                    <label className="dark:text-card-foreground  inline-flex items-center gap-0.5">
                      Index page
                      <span className="text-blue-500">
                        {unapplied && "will be"} updated
                      </span>
                    </label>
                    <div className="relative">
                      <Input
                        disabled
                        placeholder="<empty>"
                        defaultValue={new_value?.options?.index_page}
                        className={cn(
                          "disabled:bg-secondary/60",
                          "dark:disabled:bg-secondary-foreground",
                          "disabled:border-transparent disabled:opacity-100",
                          "disabled:placeholder-shown:font-mono"
                        )}
                      />
                    </div>
                  </fieldset>
                ) : (
                  <fieldset className="flex flex-col gap-1.5 flex-1">
                    <label className="dark:text-card-foreground  inline-flex items-center gap-0.5">
                      Not found page
                      <span className="text-blue-500">
                        {unapplied && "will be"} updated
                      </span>
                    </label>
                    <div className="relative">
                      <Input
                        disabled
                        placeholder="<empty>"
                        defaultValue={new_value?.options?.not_found_page}
                        className={cn(
                          "disabled:bg-secondary/60",
                          "dark:disabled:bg-secondary-foreground",
                          "disabled:border-transparent disabled:opacity-100",
                          "disabled:placeholder-shown:font-mono"
                        )}
                      />
                    </div>
                  </fieldset>
                )}

                <label>
                  Generated Caddyfile&nbsp;
                  <span className="text-blue-500">
                    {unapplied && "will be"} updated
                  </span>
                </label>
                <div
                  className={cn(
                    "resize-y h-52 min-h-52 overflow-y-auto overflow-x-clip max-w-full",
                    "w-[85dvw] sm:w-[90dvw] md:w-[380px]"
                  )}
                >
                  <Editor
                    className="w-full h-full max-w-full"
                    value={new_value?.options?.generated_caddyfile ?? ""}
                    theme="vs-dark"
                    language="ini"
                    options={{
                      readOnly: true,
                      minimap: {
                        enabled: false
                      }
                    }}
                  />
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export function PortChangeItem({ change, unapplied = false }: ChangeItemProps) {
  const new_value = change.new_value as Service["ports"][number];
  const old_value = change.old_value as Service["ports"][number];

  return (
    <div className="flex flex-col gap-2 items-center md:flex-row overflow-x-auto">
      <div
        className={cn(
          "w-full px-3 py-4 bg-muted rounded-md inline-flex gap-2 items-center text-start flex-wrap pr-24",
          {
            "dark:bg-primary-foreground bg-primary/60": change.type === "ADD",
            "dark:bg-red-500/30 bg-red-300/60": change.type === "DELETE"
          }
        )}
      >
        <span>{(old_value ?? new_value)?.host}</span>
        <ArrowRightIcon size={15} className="text-grey" />
        <span className="text-grey">{(old_value ?? new_value)?.forwarded}</span>

        {change.type === "ADD" && (
          <span className="text-green-500">{unapplied && "will be"} added</span>
        )}
        {change.type === "DELETE" && (
          <span className="text-red-500">{unapplied && "will be"} removed</span>
        )}
      </div>

      {change.type === "UPDATE" && (
        <>
          <ArrowDownIcon
            size={24}
            className="text-grey md:-rotate-90 flex-none"
          />
          <div
            className={cn(
              "w-full px-3 py-4 bg-muted rounded-md inline-flex gap-2 items-center text-start flex-wrap pr-24",
              "data-[state=open]:rounded-b-none",
              "dark:bg-secondary-foreground bg-secondary/60"
            )}
          >
            <span>{new_value.host}</span>
            <ArrowRightIcon size={15} className="text-grey" />
            <span className="text-grey">{new_value.forwarded}</span>

            <span className="text-blue-500">
              {unapplied && "will be"} updated
            </span>
          </div>
        </>
      )}
    </div>
  );
}

export function EnvVariableChangeItem({
  change,
  unapplied = false
}: ChangeItemProps) {
  const new_value = change.new_value as Service["env_variables"][number] | null;
  const old_value = change.old_value as Service["env_variables"][number] | null;

  return (
    <div className="flex flex-col gap-2 items-center md:flex-row overflow-x-auto">
      <div
        className={cn(
          "w-full px-3 py-4 bg-muted rounded-md inline-flex items-start text-start pr-24",
          "font-mono",
          {
            "dark:bg-primary-foreground bg-primary/60": change.type === "ADD",
            "dark:bg-red-500/30 bg-red-300/60": change.type === "DELETE"
          }
        )}
      >
        <span>{(old_value ?? new_value)?.key}</span>
        <span className="text-grey">{"="}</span>
        <span className={`hyphens-auto`}>
          {(old_value ?? new_value)?.value}
        </span>
        <span>&nbsp;</span>
        {change.type === "ADD" && (
          <span className="text-green-500">{unapplied && "will be"} added</span>
        )}
        {change.type === "DELETE" && (
          <span className="text-red-500">{unapplied && "will be"} removed</span>
        )}
      </div>

      {change.type === "UPDATE" && (
        <>
          <ArrowDownIcon
            size={24}
            className="text-grey md:-rotate-90 flex-none"
          />

          <div
            className={cn(
              "w-full px-3 py-4 bg-muted rounded-md inline-flex items-start text-start pr-24",
              "font-mono",
              "dark:bg-secondary-foreground bg-secondary/60"
            )}
          >
            <span>{new_value?.key}</span>
            <span className="text-grey">{"="}</span>
            <span className={`hyphens-auto`}>{new_value?.value}</span>
            <span>&nbsp;</span>
            <span className="text-blue-500">
              {unapplied && "will be"} updated
            </span>
          </div>
        </>
      )}
    </div>
  );
}

export function UrlChangeItem({ change, unapplied = false }: ChangeItemProps) {
  const new_value = change.new_value as Service["urls"][number] | null;
  const old_value = change.old_value as Service["urls"][number] | null;

  return (
    <div className="flex flex-col gap-2 items-stretch md:flex-row overflow-x-auto">
      <div
        className={cn(
          "w-full px-3 bg-muted rounded-md flex flex-col gap-2 items-start text-start flex-wrap pr-24 py-4",
          "text-base",
          {
            "dark:bg-primary-foreground bg-primary/60": change.type === "ADD",
            "dark:bg-red-500/30 bg-red-300/60": change.type === "DELETE"
          }
        )}
      >
        <p className="break-all">
          {(old_value ?? new_value)?.domain}
          <span className="text-grey">
            {(old_value ?? new_value)?.base_path ?? "/"}
          </span>
          &nbsp;
          {change.type === "ADD" && (
            <span className="text-green-500">
              {unapplied && "will be"} added
            </span>
          )}
          {change.type === "DELETE" && (
            <span className="text-red-500">
              {unapplied && "will be"} removed
            </span>
          )}
        </p>
        {(old_value ?? new_value)?.redirect_to && (
          <small className="inline-flex gap-2 items-center">
            <ArrowRightIcon size={15} className="text-grey flex-none" />
            <span className="text-grey">
              {(old_value ?? new_value)?.redirect_to?.url}
            </span>
            <span className="text-card-foreground">
              [
              {(old_value ?? new_value)?.redirect_to?.permanent
                ? "permanent redirect"
                : "temporary redirect"}
              ]
            </span>
          </small>
        )}
        {(old_value ?? new_value)?.associated_port && (
          <small className="inline-flex gap-2 items-center">
            <ArrowRightIcon size={15} className="text-grey flex-none" />
            <span className="text-grey">
              {(old_value ?? new_value)?.associated_port}
            </span>
          </small>
        )}
      </div>
      {change.type === "UPDATE" && (
        <>
          <ArrowDownIcon
            size={24}
            className="text-grey md:-rotate-90 flex-none self-center"
          />

          <div
            className={cn(
              "flex flex-col items-start text-start",
              "w-full px-3 bg-muted rounded-md inline-flex gap-2 text-start pr-24 py-4 flex-wrap",
              "dark:bg-secondary-foreground bg-secondary/60 h-full"
            )}
          >
            <div className="inline">
              <span className="break-all">
                {new_value?.domain}
                <span className="text-grey">{new_value?.base_path ?? "/"}</span>
                &nbsp;
              </span>
              <span className="text-blue-500 break-words">
                {unapplied && "will be"} updated
              </span>
            </div>
            {new_value?.redirect_to && (
              <div className="inline-flex gap-2 items-center">
                <ArrowRightIcon size={15} className="text-grey flex-none" />
                <span className="text-grey">{new_value?.redirect_to?.url}</span>
                <span className="text-foreground">
                  ({new_value.redirect_to.permanent ? "permanent" : "temporary"}
                  )
                </span>
              </div>
            )}
            {new_value?.associated_port && (
              <small className="inline-flex gap-2 items-center">
                <ArrowRightIcon size={15} className="text-grey flex-none" />
                <span className="text-grey">{new_value?.associated_port}</span>
              </small>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export function CommandChangeField({
  change,
  unapplied = false
}: ChangeItemProps) {
  const new_value = change.new_value as Service["command"] | null;
  const old_value = change.old_value as Service["command"] | null;
  return (
    <div className="flex flex-col md:flex-row gap-4 items-center overflow-x-auto">
      <span
        className={cn(
          "flex items-center text-sm p-3 flex-none min-w-fit",
          "bg-muted rounded-md"
        )}
      >
        <span>
          {old_value ?? (
            <span className="text-grey font-mono">{`<empty>`}</span>
          )}
        </span>
      </span>

      <ArrowDownIcon size={24} className="text-grey md:-rotate-90 flex-none" />
      <div className="relative flex-none min-w-fit">
        <span
          className={cn(
            "flex items-center text-sm p-3 pr-2",
            "bg-secondary/60 dark:bg-secondary-foreground rounded-md"
          )}
        >
          <span>
            {new_value ?? (
              <span className="text-grey font-mono">{`<empty>`}</span>
            )}
          </span>
          &nbsp;
          <span className="text-blue-500">
            {unapplied && "will be"} updated
          </span>
        </span>
      </div>
    </div>
  );
}

export function HealthcheckChangeField({
  change,
  unapplied = false
}: ChangeItemProps) {
  const new_value = change.new_value as Service["healthcheck"] | null;
  const old_value = change.old_value as Service["healthcheck"] | null;
  return (
    <div className="flex flex-col md:flex-row gap-4 items-center">
      <fieldset className="w-full flex flex-col gap-5">
        <div className="grid md:grid-cols-4 md:items-start gap-2 md:grid-rows-2 place-items-stretch">
          <fieldset className="grid gap-1.5 md:row-span-2 md:grid-rows-subgrid">
            <label htmlFor="healthcheck_type" className="text-muted-foreground">
              Type
            </label>
            <Input
              disabled
              placeholder="<empty>"
              className={cn(
                "disabled:placeholder-shown:font-mono bg-muted",
                "disabled:opacity-100",
                "disabled:border-transparent"
              )}
              readOnly
              value={old_value?.type}
            />
          </fieldset>
          <fieldset
            className={cn(
              "grid gap-1.5 md:row-span-2 md:grid-rows-subgrid",
              old_value?.type === "PATH" ? "md:col-span-2" : "md:col-span-3"
            )}
          >
            <label className="text-muted-foreground">Value</label>
            <Input
              disabled
              placeholder="<empty>"
              className={cn(
                "disabled:placeholder-shown:font-mono bg-muted",
                "disabled:opacity-100",
                "disabled:border-transparent"
              )}
              readOnly
              value={old_value?.value}
            />
          </fieldset>
          {old_value?.type === "PATH" && (
            <fieldset
              className={cn("grid gap-1.5 md:row-span-2 md:grid-rows-subgrid")}
            >
              <label className="text-muted-foreground">Listening port</label>
              <Input
                disabled
                placeholder="<empty>"
                className={cn(
                  "disabled:placeholder-shown:font-mono bg-muted",
                  "disabled:opacity-100",
                  "disabled:border-transparent"
                )}
                readOnly
                value={old_value?.associated_port}
              />
            </fieldset>
          )}
        </div>
        <fieldset className="flex flex-col gap-1.5 flex-1">
          <label className="text-muted-foreground">Timeout (in seconds)</label>
          <Input
            disabled
            placeholder="<empty>"
            readOnly
            value={old_value?.timeout_seconds}
            className={cn(
              "disabled:placeholder-shown:font-mono bg-muted",
              "disabled:opacity-100",
              "disabled:border-transparent"
            )}
          />
        </fieldset>
        <fieldset className="flex flex-col gap-1.5 flex-1">
          <label className="text-muted-foreground">Interval (in seconds)</label>
          <Input
            placeholder="<empty>"
            disabled
            readOnly
            value={old_value?.interval_seconds}
            className={cn(
              "disabled:placeholder-shown:font-mono bg-muted",
              "disabled:opacity-100",
              "disabled:border-transparent"
            )}
          />
        </fieldset>
      </fieldset>

      <ArrowDownIcon size={24} className="text-grey md:-rotate-90 flex-none" />

      <fieldset className="w-full flex flex-col gap-5">
        <div className="grid md:grid-cols-4 md:items-start gap-2 md:grid-rows-2 place-items-stretch">
          <fieldset className="grid gap-1.5 md:row-span-2 md:grid-rows-subgrid">
            <label htmlFor="healthcheck_type" className="text-muted-foreground">
              <span>Type</span>
              &nbsp;
              <span className="text-blue-500">
                {unapplied && "will be"} updated
              </span>
            </label>
            <Input
              disabled
              placeholder="<empty>"
              className={cn(
                "disabled:placeholder-shown:font-mono disabled:bg-secondary/60",
                "dark:disabled:bg-secondary-foreground disabled:opacity-100",
                "disabled:border-transparent"
              )}
              readOnly
              value={new_value?.type}
            />
          </fieldset>
          <fieldset
            className={cn(
              "grid gap-1.5 md:row-span-2 md:grid-rows-subgrid",
              new_value?.type === "PATH" ? "md:col-span-2" : "md:col-span-3"
            )}
          >
            <label className="text-muted-foreground">
              <span>Value</span>
              &nbsp;
              <span className="text-blue-500">
                {unapplied && "will be"} updated
              </span>
            </label>
            <Input
              disabled
              placeholder="<empty>"
              className={cn(
                "disabled:placeholder-shown:font-mono disabled:bg-secondary/60",
                "dark:disabled:bg-secondary-foreground disabled:opacity-100",
                "disabled:border-transparent"
              )}
              readOnly
              value={new_value?.value}
            />
          </fieldset>
          {new_value?.type === "PATH" && (
            <fieldset
              className={cn(
                "gap-1.5 flex-1 grid md:row-span-2 md:grid-rows-subgrid"
              )}
            >
              <label className="text-muted-foreground">
                Listening port&nbsp;
                <span className="text-blue-500">
                  {unapplied && "will be"} updated
                </span>
              </label>
              <Input
                disabled
                placeholder="<empty>"
                className={cn(
                  "disabled:placeholder-shown:font-mono disabled:bg-secondary/60",
                  "dark:disabled:bg-secondary-foreground disabled:opacity-100",
                  "disabled:border-transparent"
                )}
                readOnly
                value={new_value?.associated_port}
              />
            </fieldset>
          )}
        </div>
        <fieldset className="flex flex-col gap-1.5 flex-1">
          <label className="text-muted-foreground">
            Timeout (in seconds)&nbsp;
            <span className="text-blue-500">
              {unapplied && "will be"} updated
            </span>
          </label>
          <Input
            disabled
            placeholder="<empty>"
            readOnly
            value={new_value?.timeout_seconds}
            className={cn(
              "disabled:placeholder-shown:font-mono disabled:bg-secondary/60",
              "dark:disabled:bg-secondary-foreground disabled:opacity-100",
              "disabled:border-transparent"
            )}
          />
        </fieldset>
        <fieldset className="flex flex-col gap-1.5 flex-1">
          <label className="text-muted-foreground">
            Interval (in seconds)&nbsp;
            <span className="text-blue-500">
              {unapplied && "will be"} updated
            </span>
          </label>
          <Input
            placeholder="<empty>"
            disabled
            readOnly
            value={new_value?.interval_seconds}
            className={cn(
              "disabled:placeholder-shown:font-mono disabled:bg-secondary/60",
              "dark:disabled:bg-secondary-foreground disabled:opacity-100",
              "disabled:border-transparent"
            )}
          />
        </fieldset>
      </fieldset>
    </div>
  );
}

export function ResourceLimitChangeField({
  change,
  unapplied = false
}: ChangeItemProps) {
  const new_value = change.new_value as Service["resource_limits"] | null;
  const old_value = change.old_value as Service["resource_limits"] | null;
  return (
    <div className="flex flex-col md:flex-row gap-4 items-center">
      <div className="flex flex-col  gap-4 w-full">
        <fieldset className="flex flex-col gap-1.5 flex-1">
          <label htmlFor="healthcheck_type" className="text-muted-foreground">
            CPUs
          </label>
          <Input
            disabled
            readOnly
            placeholder="<no-limit>"
            value={old_value?.cpus}
            className={cn(
              "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
              "data-[edited]:dark:disabled:bg-secondary-foreground",
              "disabled:border-transparent disabled:opacity-100 disabled:select-none"
            )}
          />
        </fieldset>
        <fieldset className="flex flex-col gap-1.5 flex-1">
          <label htmlFor="healthcheck_type" className="text-muted-foreground">
            Memory (in MiB)
          </label>
          <Input
            disabled
            readOnly
            placeholder="<no-limit>"
            value={old_value?.memory?.value}
            className={cn(
              "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
              "data-[edited]:dark:disabled:bg-secondary-foreground",
              "disabled:border-transparent disabled:opacity-100 disabled:select-none"
            )}
          />
        </fieldset>
      </div>
      <ArrowDownIcon size={24} className="text-grey md:-rotate-90 flex-none" />
      <div className="flex flex-col  gap-4 w-full">
        <fieldset className="flex flex-col gap-1.5 flex-1">
          <label htmlFor="healthcheck_type" className="text-muted-foreground">
            CPUs&nbsp;
            <span className="text-blue-500">
              {unapplied && "will be"} updated
            </span>
          </label>
          <Input
            disabled
            readOnly
            placeholder="<no-limit>"
            data-edited
            value={new_value?.cpus}
            className={cn(
              "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
              "data-[edited]:dark:disabled:bg-secondary-foreground",
              "disabled:border-transparent disabled:opacity-100 disabled:select-none"
            )}
          />
        </fieldset>
        <fieldset className="flex flex-col gap-1.5 flex-1">
          <label htmlFor="healthcheck_type" className="text-muted-foreground">
            Memory (in MiB)&nbsp;
            <span className="text-blue-500">
              {unapplied && "will be"} updated
            </span>
          </label>
          <Input
            disabled
            readOnly
            placeholder="<no-limit>"
            data-edited
            value={new_value?.memory?.value}
            className={cn(
              "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
              "data-[edited]:dark:disabled:bg-secondary-foreground",
              "disabled:border-transparent disabled:opacity-100 disabled:select-none"
            )}
          />
        </fieldset>
      </div>
    </div>
  );
}

export function ConfigChangeItem({
  change,
  unapplied = false
}: ChangeItemProps) {
  const new_value = change.new_value as Service["configs"][number];
  const old_value = change.old_value as Service["configs"][number];

  return (
    <div className="flex flex-col gap-2 items-center overflow-x-auto">
      <div
        className={cn("rounded-md p-4 flex items-start gap-2 bg-muted w-full", {
          "dark:bg-primary-foreground bg-primary/60": change.type === "ADD",
          "dark:bg-red-500/20 bg-red-300/60": change.type === "DELETE"
        })}
      >
        <FileSlidersIcon size={20} className="text-grey relative top-1.5" />
        <div className="flex flex-col gap-2 w-full">
          <h3 className="text-lg inline-flex gap-1 items-center">
            <span>{(old_value ?? new_value).name}</span>
            {change.type === "ADD" && (
              <span className="text-green-500">
                {unapplied && "will be"} added
              </span>
            )}
            {change.type === "DELETE" && (
              <span className="text-red-500">
                {unapplied && "will be"} removed
              </span>
            )}
          </h3>
          <small className="text-card-foreground inline-flex gap-1 items-center">
            <span className="text-grey">
              {(old_value ?? new_value).mount_path}
            </span>
          </small>

          <div
            className={cn(
              "resize-y h-52 min-h-52 overflow-y-auto overflow-x-clip max-w-full w-full"
            )}
          >
            <Editor
              className="w-full h-full max-w-full"
              language={(old_value ?? new_value).language}
              value={(old_value ?? new_value).contents}
              theme="vs-dark"
              options={{
                readOnly: true,
                minimap: {
                  enabled: false
                }
              }}
            />
          </div>
        </div>
      </div>

      {change.type === "UPDATE" && (
        <>
          <ArrowDownIcon size={24} className="text-grey flex-none" />

          <div
            className={cn(
              "rounded-md p-4 flex items-start gap-2 bg-muted w-full",
              "dark:bg-secondary-foreground bg-secondary/60"
            )}
          >
            <FileSlidersIcon size={20} className="text-grey relative top-1.5" />
            <div className="flex flex-col gap-2 w-full">
              <h3 className="text-lg inline-flex gap-1 items-center">
                <span>{new_value.name}</span>
                <span className="text-blue-500">
                  {unapplied && "will be"} updated
                </span>
              </h3>
              <small className="text-card-foreground inline-flex gap-1 items-center">
                <span className="text-grey">{new_value.mount_path}</span>
              </small>

              <div
                className={cn(
                  "resize-y h-52 min-h-52 overflow-y-auto overflow-x-clip max-w-full w-full"
                )}
              >
                <Editor
                  className="w-full h-full max-w-full"
                  language={new_value.language}
                  value={new_value.contents}
                  theme="vs-dark"
                  options={{
                    readOnly: true,
                    minimap: {
                      enabled: false
                    }
                  }}
                />
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
