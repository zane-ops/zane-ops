import hljs from "highlight.js/lib/core";
import json from "highlight.js/lib/languages/json";
import {
  ActivityIcon,
  BookmarkIcon,
  CheckIcon,
  ChevronRightIcon,
  ClockIcon,
  ContainerIcon,
  CopyIcon,
  EthernetPortIcon,
  ExternalLinkIcon,
  FileSliders,
  FilmIcon,
  GitCommitIcon,
  GitCompareArrowsIcon,
  GithubIcon,
  GlobeIcon,
  HammerIcon,
  HardDriveIcon,
  HashIcon,
  HourglassIcon,
  InfoIcon,
  KeyRoundIcon,
  LoaderIcon,
  MessageCircleCode,
  RocketIcon,
  TagIcon,
  TerminalIcon,
  TrendingUpIcon,
  UserIcon
} from "lucide-react";
import * as React from "react";
import { Link } from "react-router";
import { StatusBadge } from "~/components/status-badge";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
import {
  capitalizeText,
  formatElapsedTime,
  formattedTime,
  wait
} from "~/utils";
import { type Route } from "./+types/deployment-details";
import "highlight.js/styles/atom-one-dark.css";
import { useQuery } from "@tanstack/react-query";
import {
  BuilderChangeField,
  CommandChangeField,
  ConfigChangeItem,
  EnvVariableChangeItem,
  GitSourceChangeField,
  HealthcheckChangeField,
  PortChangeItem,
  ResourceLimitChangeField,
  SourceChangeField,
  UrlChangeItem,
  VolumeChangeItem
} from "~/components/change-fields";
import { Code } from "~/components/code";
import { Button } from "~/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import {
  type Deployment,
  type Service,
  deploymentQueries
} from "~/lib/queries";
import { cn } from "~/lib/utils";

hljs.registerLanguage("json", json);

export default function DeploymentDetailsPage({
  params: {
    projectSlug: project_slug,
    serviceSlug: service_slug,
    deploymentHash: deployment_hash,
    envSlug: env_slug
  },
  matches: {
    "2": { loaderData: initialData }
  }
}: Route.ComponentProps) {
  const { data: deployment } = useQuery({
    ...deploymentQueries.single({
      project_slug,
      service_slug,
      env_slug,
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
  const imageParts = serviceImage?.split(":") ?? [];
  const tag = imageParts.length > 1 ? imageParts.pop() : "latest";
  const image = imageParts.join(":");

  const repoUrl = deployment.service_snapshot.repository_url
    ? new URL(deployment.service_snapshot.repository_url)
    : null;

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
    Service["unapplied_changes"][number]["field"],
    React.ComponentType<React.ComponentProps<typeof HardDriveIcon>>
  > = {
    source: ContainerIcon,
    git_source: GitCompareArrowsIcon,
    builder: HammerIcon,
    volumes: HardDriveIcon,
    ports: EthernetPortIcon,
    command: TerminalIcon,
    env_variables: KeyRoundIcon,
    urls: GlobeIcon,
    resource_limits: HourglassIcon,
    healthcheck: ActivityIcon,
    configs: FileSliders
  };
  const [hasCopied, startTransition] = React.useTransition();

  const trigger_method_map: Record<Deployment["trigger_method"], string> = {
    AUTO: "automatic deploy on git push",
    API: "Using deploy webhook URL",
    MANUAL: "manual"
  };

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

            {deployment.service_snapshot.type === "DOCKER_REGISTRY" && (
              <div className="flex items-center gap-2">
                <dt className="flex gap-1 items-center text-grey">
                  <TagIcon size={15} /> <span>Image:</span>
                </dt>
                <dd>
                  <span>{image}</span>
                  <span className="text-grey">:{tag}</span>
                </dd>
              </div>
            )}
            {deployment.service_snapshot.type === "GIT_REPOSITORY" && (
              <div className="flex items-center gap-2">
                <dt className="flex gap-1 items-center text-grey">
                  <GithubIcon size={15} /> <span>Repository URL:</span>
                </dt>
                <dd>
                  <a
                    href={deployment.service_snapshot.repository_url ?? "#"}
                    target="_blank"
                    className="underline text-link inline-flex gap-1 items-center"
                  >
                    {deployment.service_snapshot.repository_url}{" "}
                    <ExternalLinkIcon size={15} />
                  </a>
                </dd>
              </div>
            )}

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
            <div className="flex items-center gap-2">
              <dt className="flex gap-1 items-center text-grey">
                <RocketIcon size={15} /> <span>Trigger method:</span>
              </dt>
              <dd>{trigger_method_map[deployment.trigger_method]}</dd>
            </div>
            {deployment.started_at && (
              <div className="flex items-center gap-2">
                <dt className="flex gap-1 items-center text-grey">
                  {!deployment.finished_at ? (
                    <LoaderIcon size={15} className="animate-spin" />
                  ) : (
                    <ClockIcon size={15} />
                  )}
                  <span>Full deployment duration:</span>
                </dt>
                <dd className="flex items-center gap-1">
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
                </dd>
              </div>
            )}

            {deployment.build_started_at && deployment.build_finished_at && (
              <div className="flex items-center gap-2">
                <dt className="flex gap-1 items-center text-grey">
                  <HammerIcon size={15} />
                  <span>Build duration:</span>
                </dt>
                <dd className="flex items-center gap-1">
                  <span>
                    {formatElapsedTime(
                      Math.round(
                        (new Date(deployment.build_finished_at).getTime() -
                          new Date(deployment.build_started_at).getTime()) /
                          1000
                      ),
                      "long"
                    )}
                  </span>
                </dd>
              </div>
            )}

            {deployment.commit_sha && (
              <div className="flex items-center gap-2">
                <dt className="flex gap-1 items-center text-grey">
                  <GitCommitIcon size={15} /> <span>Git commit SHA:</span>
                </dt>
                <dd>{deployment.commit_sha}</dd>
              </div>
            )}

            {deployment.commit_author_name && (
              <div className="flex items-center gap-2">
                <dt className="flex gap-1 items-center text-grey">
                  <UserIcon size={15} /> <span>Commit author:</span>
                </dt>
                <dd>{deployment.commit_author_name}</dd>
              </div>
            )}
            <div className="flex flex-col items-start gap-2">
              <dt className="flex gap-1 items-center text-grey">
                <MessageCircleCode size={15} />
                <span>Full commit message:</span>
              </dt>
              <dd className="w-full">
                <pre className="font-mono bg-muted/25 dark:bg-card p-2 rounded-md text-sm">
                  {deployment.commit_message}
                </pre>
              </dd>
            </div>
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
                  {field === "git_source" &&
                    changes.map((change) => (
                      <React.Fragment key={change.id}>
                        <GitSourceChangeField change={change} />
                        <hr className="border border-dashed border-border" />
                      </React.Fragment>
                    ))}
                  {field === "builder" &&
                    changes.map((change) => (
                      <React.Fragment key={change.id}>
                        <BuilderChangeField change={change} />
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
                <div className="overflow-x-auto max-w-full shrink min-w-0 bg-card rounded-md p-2 grow relative">
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          className="px-2.5 py-0.5 absolute top-2 right-2"
                          onClick={() => {
                            navigator.clipboard
                              .writeText(
                                JSON.stringify(
                                  deployment.service_snapshot,
                                  null,
                                  2
                                )
                              )
                              .then(() => {
                                console.log("copied !");
                                // show pending state (which is success state), until the user has stopped clicking the button
                                startTransition(() => wait(1000));
                              });
                          }}
                        >
                          {hasCopied ? (
                            <CheckIcon size={15} className="flex-none" />
                          ) : (
                            <CopyIcon size={15} className="flex-none" />
                          )}
                          <span className="sr-only">Copy</span>
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Copy</TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
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
