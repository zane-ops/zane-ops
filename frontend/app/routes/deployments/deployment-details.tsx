import hljs from "highlight.js/lib/core";
import json from "highlight.js/lib/languages/json";
import {
  ArrowDown,
  ArrowDownIcon,
  ArrowRightIcon,
  BookmarkIcon,
  ChevronRightIcon,
  CircleStopIcon,
  ContainerIcon,
  EthernetPortIcon,
  EyeIcon,
  EyeOffIcon,
  FilmIcon,
  GitCompareArrowsIcon,
  GlobeIcon,
  HardDriveIcon,
  HashIcon,
  InfoIcon,
  KeyRoundIcon,
  LoaderIcon,
  PlayIcon,
  PlugIcon,
  TagIcon,
  TerminalIcon,
  TimerIcon,
  ToyBrickIcon,
  TrendingUpIcon
} from "lucide-react";
import * as React from "react";
import { Link } from "react-router";
import { Code } from "~/components/code";
import { StatusBadge } from "~/components/status-badge";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
import { Alert } from "~/components/ui/alert";
import {
  capitalizeText,
  formatElapsedTime,
  formattedTime,
  pluralize
} from "~/utils";
import { type Route } from "./+types/deployment-details";
import "highlight.js/styles/atom-one-dark.css";
import { useQuery } from "@tanstack/react-query";
import type { Button } from "react-day-picker";
import { Input } from "~/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { type DockerService, deploymentQueries } from "~/lib/queries";
import type { ValueOf } from "~/lib/types";
import { cn } from "~/lib/utils";

hljs.registerLanguage("json", json);

export default function DeploymentDetailsPage({
  params: {
    projectSlug: project_slug,
    serviceSlug: service_slug,
    deploymentHash: deployment_hash
  },
  matches: {
    "2": { data: initialData }
  }
}: Route.ComponentProps) {
  const { data: deployment } = useQuery({
    ...deploymentQueries.single({
      project_slug,
      service_slug,
      deployment_hash
    }),
    initialData: initialData.deployment
  });

  const now = new Date();
  const [timeElapsed, setTimeElapsed] = React.useState(
    deployment.started_at
      ? Math.ceil(
          (now.getTime() - new Date(deployment.started_at).getTime()) / 1000
        )
      : 0
  );

  const highlightedCode = hljs.highlight(
    JSON.stringify(deployment.service_snapshot, null, 2),
    { language: "json" }
  ).value;

  const deploymentChanges = Object.groupBy(
    deployment.changes,
    ({ field }) => field
  );

  const serviceImage = deployment.service_snapshot.image;
  const imageParts = serviceImage.split(":");
  const tag = imageParts.length > 1 ? imageParts.pop() : "latest";
  const image = imageParts.join(":");

  React.useEffect(() => {
    if (deployment.started_at && !deployment.finished_at) {
      const timer = setInterval(() => {
        setTimeElapsed(() =>
          Math.ceil(
            (new Date().getTime() -
              new Date(deployment.started_at!).getTime()) /
              1000
          )
        );
      }, 1000);

      return () => clearInterval(timer);
    }
  }, [deployment.started_at, deployment.finished_at]);

  const IconFieldMap: Record<
    DockerService["unapplied_changes"][number]["field"],
    React.ComponentType<React.ComponentProps<typeof HardDriveIcon>>
  > = {
    source: ContainerIcon,
    volumes: HardDriveIcon,
    ports: EthernetPortIcon,
    command: TerminalIcon,
    env_variables: KeyRoundIcon,
    urls: GlobeIcon
  };

  console.log({
    changes: deployment.changes
  });

  return (
    <div className="my-6 flex flex-col lg:w-4/5">
      <section id="details" className="flex gap-1 scroll-mt-20">
        <div className="w-16 hidden md:flex flex-col items-center">
          <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
            <InfoIcon size={15} className="flex-none text-grey" />
          </div>
          <div className="h-full border border-grey/50"></div>
        </div>

        <div className="w-full flex flex-col gap-5 pt-1 pb-8">
          <h2 className="text-lg text-grey">Details</h2>
          <dl className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <dt className="flex gap-1 items-center text-grey">
                <HashIcon size={15} /> <span>Hash:</span>
              </dt>
              <dd>{deployment.hash}</dd>
              {deployment.redeploy_hash && (
                <span className="text-grey">
                  (Redeploy of&nbsp;
                  <Link
                    to={`/project/${project_slug}/services/${service_slug}/deployments/${deployment.redeploy_hash}`}
                    className="text-link underline"
                  >
                    #{deployment.redeploy_hash}
                  </Link>
                  )
                </span>
              )}
            </div>

            <div className="flex items-center gap-2">
              <dt className="flex gap-1 items-center text-grey">
                <TagIcon size={15} /> <span>Image:</span>
              </dt>
              <dd>
                <span>{image}</span>
                <span className="text-grey">:{tag}</span>
              </dd>
            </div>

            <div className="flex items-center gap-2">
              <dt className="flex gap-1 items-center text-grey">
                <BookmarkIcon size={15} /> <span>Slot:</span>
              </dt>
              <dd>
                <StatusBadge
                  color={deployment.slot === "BLUE" ? "blue" : "green"}
                  pingState="static"
                >
                  {deployment.slot}
                </StatusBadge>
              </dd>
            </div>

            <div className="flex items-center gap-2">
              <dt className="flex gap-1 items-center text-grey">
                <TrendingUpIcon size={15} /> <span>Queued at:</span>
              </dt>
              <dd>{formattedTime(deployment.queued_at)}</dd>
            </div>
            {deployment.started_at && (
              <div className="flex items-center gap-2">
                <dt className="flex gap-1 items-center text-grey">
                  {!deployment.finished_at ? (
                    <LoaderIcon size={15} className="animate-spin" />
                  ) : (
                    <PlayIcon size={15} />
                  )}
                  <span>Duration:</span>
                </dt>
                <dd className="flex items-center gap-1">
                  <span>{formattedTime(deployment.started_at)}</span>
                  <span className="text-grey">-</span>
                  {deployment.finished_at && (
                    <span>{formattedTime(deployment.finished_at)}</span>
                  )}

                  <span className="text-grey">
                    {"("}
                    {deployment.started_at && !deployment.finished_at ? (
                      <span>{formatElapsedTime(timeElapsed)}</span>
                    ) : (
                      deployment.started_at &&
                      deployment.finished_at && (
                        <span>
                          {formatElapsedTime(
                            Math.round(
                              (new Date(deployment.finished_at).getTime() -
                                new Date(deployment.started_at).getTime()) /
                                1000
                            ),
                            "long"
                          )}
                        </span>
                      )
                    )}
                    {")"}
                  </span>
                </dd>
              </div>
            )}

            {/* {deployment.finished_at && (
              <div className="flex items-center gap-2">
                <dt className="flex gap-1 items-center text-grey">
                  <CircleStopIcon size={15} /> <span>Finished at:</span>
                </dt>
                <dd>{formattedTime(deployment.finished_at)}</dd>
              </div>
            )} */}

            {/* <div className="flex items-center gap-2">
              <dt className="flex gap-1 items-center text-grey">
                <TimerIcon size={15} className="flex-none" />
                <span>Total duration:</span>
              </dt>
              <dd>
                {deployment.started_at && !deployment.finished_at ? (
                  <span>{formatElapsedTime(timeElapsed)}</span>
                ) : deployment.started_at && deployment.finished_at ? (
                  <span>
                    {formatElapsedTime(
                      Math.round(
                        (new Date(deployment.finished_at).getTime() -
                          new Date(deployment.started_at).getTime()) /
                          1000
                      )
                    )}
                  </span>
                ) : (
                  <span>-</span>
                )}
              </dd>
            </div> */}
          </dl>
        </div>
      </section>

      <section id="changes" className="flex gap-1 scroll-mt-20">
        <div className="w-16 hidden md:flex flex-col items-center">
          <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
            <GitCompareArrowsIcon size={15} className="flex-none text-grey" />
          </div>
          <div className="h-full border border-grey/50"></div>
        </div>

        <div className="w-full flex flex-col gap-5 pt-1 pb-8">
          <h2 className="text-lg text-grey">Changes</h2>
          <p className="text-gray-400">
            All the changes applied by this deployment.
          </p>

          {deployment.changes.length === 0 && (
            <div
              className={cn(
                "border-dashed border border-foreground rounded-md px-4 py-8 font-mono",
                "flex items-center justify-center text-foreground"
              )}
            >
              No changes made in this deployment
            </div>
          )}
          {Object.entries(deploymentChanges).map((item) => {
            const field = item[0] as keyof typeof deploymentChanges;
            const changes = item[1] as NonNullable<
              (typeof deploymentChanges)[typeof field]
            >;
            const Icon = IconFieldMap[field];
            return (
              <div key={field} className="flex flex-col gap-1.5 flex-1">
                <h3 className="text-lg flex gap-2 items-center border-b py-2 border-border">
                  <Icon size={15} className="flex-none text-grey" />
                  <span>{capitalizeText(field.replaceAll("_", " "))}</span>
                </h3>
                <div className="pl-4 py-2 flex flex-col gap-2">
                  {field === "volumes" &&
                    changes.map((change) => (
                      <React.Fragment key={change.id}>
                        <VolumeChangeItem change={change} />
                        <hr className="border border-dashed border-border" />
                      </React.Fragment>
                    ))}
                  {field === "source" &&
                    changes.map((change) => (
                      <React.Fragment key={change.id}>
                        <SourceChangeField change={change} />
                        <hr className="border border-dashed border-border" />
                      </React.Fragment>
                    ))}
                  {field === "ports" &&
                    changes.map((change) => (
                      <React.Fragment key={change.id}>
                        <PortChangeItem change={change} />
                        <hr className="border border-dashed border-border" />
                      </React.Fragment>
                    ))}
                  {field === "env_variables" &&
                    changes.map((change) => (
                      <React.Fragment key={change.id}>
                        <EnvVariableChangeItem
                          change={change}
                          key={change.id}
                        />
                        <hr className="border border-dashed border-border" />
                      </React.Fragment>
                    ))}
                  {field === "urls" &&
                    changes.map((change) => (
                      <React.Fragment key={change.id}>
                        <UrlChangeItem change={change} key={change.id} />
                        <hr className="border border-dashed border-border" />
                      </React.Fragment>
                    ))}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section id="snapshot" className="flex gap-1 scroll-mt-20">
        <div className="w-16 hidden md:flex flex-col items-center">
          <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
            <FilmIcon size={15} className="flex-none text-grey" />
          </div>
        </div>

        <div className="shrink min-w-0 flex flex-col gap-5 pt-1 pb-14 w-full">
          <h2 className="text-lg text-grey">Snapshot</h2>
          <p className="text-gray-400">
            The status of the service at the time of the deployment.
          </p>
          <Accordion
            type="single"
            collapsible
            className="border-y border-border w-full"
          >
            <AccordionItem value="system">
              <AccordionTrigger className="text-muted-foreground font-normal text-sm hover:underline">
                <ChevronRightIcon className="h-4 w-4 shrink-0 transition-transform duration-200" />
                JSON structure
              </AccordionTrigger>
              <AccordionContent className="flex flex-col gap-2">
                <div className="overflow-x-auto max-w-full shrink min-w-0 bg-card rounded-md p-2 grow">
                  <pre
                    className="text-sm [&_.hljs-punctuation]:text-white dark:[&_.hljs-punctuation]:text-foreground"
                    dangerouslySetInnerHTML={{
                      __html: highlightedCode
                    }}
                  />
                </div>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </div>
      </section>
    </div>
  );
}

type ChangeItemProps = {
  change: DockerService["unapplied_changes"][number];
};
function VolumeChangeItem({ change }: ChangeItemProps) {
  const new_value = change.new_value as DockerService["volumes"][number];
  const old_value = change.old_value as DockerService["volumes"][number];

  function getModeSuffix(value: DockerService["volumes"][number]) {
    return value.mode === "READ_ONLY" ? "read only" : "read & write";
  }

  return (
    <div className="flex flex-col md:flex-row gap-2 items-center">
      <div
        className={cn("rounded-md p-4 flex items-start gap-2 bg-muted w-full", {
          "dark:bg-primary-foreground bg-primary/60": change.type === "ADD",
          "dark:bg-red-500/20 bg-red-400/60": change.type === "DELETE"
        })}
      >
        <HardDriveIcon size={20} className="text-grey relative top-1.5" />
        <div className="flex flex-col gap-2">
          <h3 className="text-lg inline-flex gap-1 items-center">
            <span>{(old_value ?? new_value).name}</span>
            {change.type === "ADD" && (
              <span className="text-green-500">added</span>
            )}
            {change.type === "DELETE" && (
              <span className="text-red-500">removed</span>
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
                <span className="text-blue-500">updated</span>
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

function SourceChangeField({ change }: ChangeItemProps) {
  const new_value = change.new_value as Pick<
    DockerService,
    "image" | "credentials"
  >;
  const old_value = change.old_value as Pick<
    DockerService,
    "image" | "credentials"
  >;

  function getImageParts(image: string) {
    const serviceImage = image;
    const imageParts = serviceImage.split(":");
    const tag = imageParts.length > 1 ? imageParts.pop() : "latest";
    const docker_image = imageParts.join(":");
    return {
      image: docker_image,
      tag
    };
  }

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
            Source Image <span className="text-blue-500">updated</span>
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
                "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
                "data-[edited]:dark:disabled:bg-secondary-foreground",
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
            Credentials <span className="text-blue-500">updated</span>
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
                id="credentials.password"
                value={new_value?.credentials?.password}
                readOnly
                data-edited
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
    </div>
  );
}

function PortChangeItem({ change }: ChangeItemProps) {
  const new_value = change.new_value as DockerService["ports"][number];
  const old_value = change.old_value as DockerService["ports"][number];

  return (
    <div className="flex flex-col gap-2 items-center">
      <div
        className={cn(
          "w-full px-3 py-4 bg-muted rounded-md inline-flex gap-2 items-center text-start flex-wrap pr-24",
          {
            "dark:bg-primary-foreground bg-primary/60": change.type === "ADD",
            "dark:bg-red-500/30 bg-red-400/60": change.type === "DELETE"
          }
        )}
      >
        <span>{(old_value ?? new_value)?.host}</span>
        <ArrowRightIcon size={15} className="text-grey" />
        <span className="text-grey">{(old_value ?? new_value)?.forwarded}</span>

        {change.type === "ADD" && <span className="text-green-500">added</span>}
        {change.type === "DELETE" && (
          <span className="text-red-500">removed</span>
        )}
      </div>

      {change.type === "UPDATE" && (
        <>
          <ArrowDownIcon size={15} className="text-grey" />
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

            <span className="text-blue-500">updated</span>
          </div>
        </>
      )}
    </div>
  );
}

function EnvVariableChangeItem({ change }: ChangeItemProps) {
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
            "dark:bg-red-500/30 bg-red-400/60": change.type === "DELETE"
          }
        )}
      >
        <span>{(old_value ?? new_value)?.key}</span>
        <span className="text-grey">{"="}</span>
        <span>{(old_value ?? new_value)?.value}</span>
        <span>&nbsp;</span>
        {change.type === "ADD" && <span className="text-green-500">added</span>}
        {change.type === "DELETE" && (
          <span className="text-red-500">removed</span>
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
            <span>{new_value?.value}</span>
            <span>&nbsp;</span>
            <span className="text-blue-500">updated</span>
          </div>
        </>
      )}
    </div>
  );
}

function UrlChangeItem({ change }: ChangeItemProps) {
  const new_value = change.new_value as DockerService["urls"][number] | null;
  const old_value = change.old_value as DockerService["urls"][number] | null;

  return (
    <div className="flex flex-col gap-2 items-center md:flex-row">
      <div
        className={cn(
          "w-full px-3 bg-muted rounded-md inline-flex gap-2 items-center text-start flex-wrap pr-24 py-4",
          {
            "dark:bg-primary-foreground bg-primary/60": change.type === "ADD",
            "dark:bg-red-500/30 bg-red-400/60": change.type === "DELETE"
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

        {change.type === "ADD" && <span className="text-green-500">added</span>}
        {change.type === "DELETE" && (
          <span className="text-red-500">removed</span>
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

            <span className="text-blue-500">updated</span>
          </div>
        </>
      )}
    </div>
  );
}
