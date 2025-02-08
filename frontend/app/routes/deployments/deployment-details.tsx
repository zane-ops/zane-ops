import hljs from "highlight.js/lib/core";
import json from "highlight.js/lib/languages/json";
import {
  ActivityIcon,
  BookmarkIcon,
  ChevronRightIcon,
  ContainerIcon,
  EthernetPortIcon,
  FileSliders,
  FilmIcon,
  GitCompareArrowsIcon,
  GlobeIcon,
  HardDriveIcon,
  HashIcon,
  HourglassIcon,
  InfoIcon,
  KeyRoundIcon,
  LoaderIcon,
  PlayIcon,
  TagIcon,
  TerminalIcon,
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
import { capitalizeText, formatElapsedTime, formattedTime } from "~/utils";
import { type Route } from "./+types/deployment-details";
import "highlight.js/styles/atom-one-dark.css";
import { useQuery } from "@tanstack/react-query";
import {
  CommandChangeField,
  ConfigChangeItem,
  EnvVariableChangeItem,
  HealthcheckChangeField,
  PortChangeItem,
  ResourceLimitChangeField,
  SourceChangeField,
  UrlChangeItem,
  VolumeChangeItem
} from "~/components/change-fields";
import { type DockerService, deploymentQueries } from "~/lib/queries";
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

  const changes = deployment.changes.map((ch) => {
    // @ts-expect-error : this is to support old versions of the changes fields
    if (ch.field === "image") {
      return {
        ...ch,
        field: "source",
        new_value: { image: ch.new_value },
        old_value: { image: ch.old_value }
      } as (typeof deployment.changes)[number];
    }
    // @ts-expect-error : this is to support old versions of the changes fields
    if (ch.field === "credentials") {
      return {
        ...ch,
        field: "source",
        new_value: { credentials: ch.new_value },
        old_value: { credentials: ch.old_value }
      } as (typeof deployment.changes)[number];
    }

    return ch;
  });

  const deploymentChanges = Object.groupBy(changes, ({ field }) => field);

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
    urls: GlobeIcon,
    resource_limits: HourglassIcon,
    healthcheck: ActivityIcon,
    configs: FileSliders
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

          {changes.length === 0 && (
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
            const fieldName = field === "configs" ? "Config files" : field;
            return (
              <div key={field} className="flex flex-col gap-1.5 flex-1">
                <h3 className="text-lg flex gap-2 items-center border-b py-2 border-border">
                  <Icon size={15} className="flex-none text-grey" />
                  <span>{capitalizeText(fieldName.replaceAll("_", " "))}</span>
                </h3>
                <div className="pl-4 py-2 flex flex-col gap-2">
                  {field === "volumes" &&
                    changes.map((change) => (
                      <React.Fragment key={change.id}>
                        <VolumeChangeItem change={change} />
                        <hr className="border border-dashed border-border" />
                      </React.Fragment>
                    ))}
                  {field === "configs" &&
                    changes.map((change) => (
                      <React.Fragment key={change.id}>
                        <ConfigChangeItem change={change} />
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
                  {field === "command" &&
                    changes.map((change) => (
                      <React.Fragment key={change.id}>
                        <CommandChangeField change={change} />
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
                  {field === "healthcheck" &&
                    changes.map((change) => (
                      <React.Fragment key={change.id}>
                        <HealthcheckChangeField
                          change={change}
                          key={change.id}
                        />
                        <hr className="border border-dashed border-border" />
                      </React.Fragment>
                    ))}
                  {field === "resource_limits" &&
                    changes.map((change) => (
                      <React.Fragment key={change.id}>
                        <ResourceLimitChangeField
                          change={change}
                          key={change.id}
                        />
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
