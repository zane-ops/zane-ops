import { ArrowDownIcon, ArrowRightIcon, HardDriveIcon } from "lucide-react";
import { Code } from "~/components/code";
import { Input } from "~/components/ui/input";
import type { DockerService } from "~/lib/queries";
import { cn } from "~/lib/utils";

export type ChangeItemProps = {
  change: DockerService["unapplied_changes"][number];
  unapplied?: boolean;
};

export function VolumeChangeItem({
  change,
  unapplied = false
}: ChangeItemProps) {
  const new_value = change.new_value as DockerService["volumes"][number];
  const old_value = change.old_value as DockerService["volumes"][number];

  const getModeSuffix = (value: DockerService["volumes"][number]) => {
    return value.mode === "READ_ONLY" ? "read only" : "read & write";
  };

  return (
    <div className="flex flex-col md:flex-row gap-2 items-center">
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
  const new_value = change.new_value as Pick<
    DockerService,
    "image" | "credentials"
  >;
  const old_value = change.old_value as Pick<
    DockerService,
    "image" | "credentials"
  >;

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
    <div className="flex flex-col md:flex-row gap-4 items-center">
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

export function PortChangeItem({ change, unapplied = false }: ChangeItemProps) {
  const new_value = change.new_value as DockerService["ports"][number];
  const old_value = change.old_value as DockerService["ports"][number];

  return (
    <div className="flex flex-col gap-2 items-center md:flex-row">
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
  const new_value = change.new_value as
    | DockerService["env_variables"][number]
    | null;
  const old_value = change.old_value as
    | DockerService["env_variables"][number]
    | null;

  return (
    <div className="flex flex-col gap-2 items-center md:flex-row">
      <div
        className={cn(
          "w-full px-3 py-4 bg-muted rounded-md inline-flex items-center text-start pr-24",
          "font-mono",

          {
            "dark:bg-primary-foreground bg-primary/60": change.type === "ADD",
            "dark:bg-red-500/30 bg-red-300/60": change.type === "DELETE"
          }
        )}
      >
        <span>{(old_value ?? new_value)?.key}</span>
        <span className="text-grey">{"="}</span>
        <span>
          <span className="text-grey">'</span>
          {(old_value ?? new_value)?.value}
          <span className="text-grey">'</span>
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
              "w-full px-3 py-4 bg-muted rounded-md inline-flex items-center text-start pr-24",
              "font-mono",
              "dark:bg-secondary-foreground bg-secondary/60"
            )}
          >
            <span>{new_value?.key}</span>
            <span className="text-grey">{"="}</span>
            <span>
              <span className="text-grey">'</span>
              {new_value?.value}
              <span className="text-grey">'</span>
            </span>
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
  const new_value = change.new_value as DockerService["urls"][number] | null;
  const old_value = change.old_value as DockerService["urls"][number] | null;

  return (
    <div className="flex flex-col gap-2 items-center md:flex-row">
      <div
        className={cn(
          "w-full px-3 bg-muted rounded-md inline-flex gap-2 items-center text-start flex-wrap pr-24 py-4",
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
        </p>
        {(old_value ?? new_value)?.redirect_to && (
          <div className="inline-flex gap-2 items-center">
            <ArrowRightIcon size={15} className="text-grey flex-none" />
            <span className="text-grey">
              {(old_value ?? new_value)?.redirect_to?.url}
            </span>
            <span className="text-foreground">
              (
              {(old_value ?? new_value)?.redirect_to?.permanent
                ? "permanent"
                : "temporary"}
              )
            </span>
          </div>
        )}

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
              "w-full px-3 bg-muted rounded-md inline-flex gap-2 items-center text-start pr-24 py-4 flex-wrap",
              "dark:bg-secondary-foreground bg-secondary/60 h-full"
            )}
          >
            <p className="break-all">
              {new_value?.domain}
              <span className="text-grey">{new_value?.base_path ?? "/"}</span>
            </p>
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

            <span className="text-blue-500">
              {unapplied && "will be"} updated
            </span>
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
  const new_value = change.new_value as DockerService["command"] | null;
  const old_value = change.old_value as DockerService["command"] | null;
  return (
    <div className="flex flex-col md:flex-row gap-4 items-center">
      <Input
        placeholder="<empty>"
        disabled
        readOnly
        value={old_value}
        className={cn(
          "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
          "data-[edited]:dark:disabled:bg-secondary-foreground",
          "disabled:border-transparent disabled:opacity-100 disabled:select-none"
        )}
      />

      <ArrowDownIcon size={24} className="text-grey md:-rotate-90 flex-none" />
      <div className="relative w-full">
        <Input
          placeholder="<empty>"
          disabled
          readOnly
          data-edited
          value={new_value}
          className={cn(
            "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
            "data-[edited]:dark:disabled:bg-secondary-foreground",
            "disabled:border-transparent disabled:opacity-100 disabled:select-none",
            "text-transparent placeholder:text-transparent"
          )}
        />
        <span className="absolute inset-y-0 left-3 flex items-center pr-2 text-sm">
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
  const new_value = change.new_value as DockerService["healthcheck"] | null;
  const old_value = change.old_value as DockerService["healthcheck"] | null;
  return (
    <div className="flex flex-col md:flex-row gap-4 items-center">
      <fieldset className="w-full flex flex-col gap-5">
        <div className="flex flex-col md:flex-row md:items-start gap-2">
          <fieldset className="flex flex-col gap-1.5 flex-1">
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
          <fieldset className="flex flex-col gap-1.5 flex-1">
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
        <div className="flex flex-col md:flex-row md:items-start gap-2">
          <fieldset className="flex flex-col gap-1.5 flex-1">
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
          <fieldset className="flex flex-col gap-1.5 flex-1">
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
  const new_value = change.new_value as DockerService["resource_limits"] | null;
  const old_value = change.old_value as DockerService["resource_limits"] | null;
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
