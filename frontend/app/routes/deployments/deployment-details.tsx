import hljs from "highlight.js/lib/core";
import json from "highlight.js/lib/languages/json";
import {
  ArrowDown,
  ArrowDownIcon,
  ArrowRightIcon,
  BookmarkIcon,
  ChevronRightIcon,
  CircleStopIcon,
  FilmIcon,
  GitCompareArrowsIcon,
  HardDriveIcon,
  HashIcon,
  InfoIcon,
  PlayIcon,
  TagIcon,
  TimerIcon,
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
import type { DockerService } from "~/lib/queries";
import type { ValueOf } from "~/lib/types";
import { cn } from "~/lib/utils";

hljs.registerLanguage("json", json);

export default function DeploymentDetailsPage({
  params,
  matches: {
    "2": {
      data: { deployment }
    }
  }
}: Route.ComponentProps) {
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
  console.log({
    changes: deploymentChanges
  });

  const serviceImage = deployment.service_snapshot.image;
  const imageParts = serviceImage.split(":");
  const tag = imageParts.length > 1 ? imageParts.pop() : "latest";
  const image = imageParts.join(":");

  return (
    <div className="my-6 flex flex-col lg:w-2/3">
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
                    to={`/project/${params.projectSlug}/services/${params.serviceSlug}/deployments/${deployment.redeploy_hash}`}
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
                  <PlayIcon size={15} /> <span>Duration:</span>
                </dt>
                <dd className="flex items-center gap-1">
                  <span>{formattedTime(deployment.started_at)}</span>
                  <span className="text-grey">-</span>
                  {deployment.finished_at && (
                    <dd>{formattedTime(deployment.finished_at)}</dd>
                  )}
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

            <div className="flex items-center gap-2">
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

          {deployment.changes.length === 0 && (
            <div
              className={cn(
                "border-dashed border border-border rounded-md px-4 py-8 font-mono",
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
            return (
              <div key={field} className="flex flex-col gap-1.5 flex-1">
                <h3>{capitalizeText(field.replaceAll("_", " "))}</h3>
                {field === "volumes" &&
                  changes.map((change) => (
                    <VolumeChangeItem change={change} key={change.id} />
                  ))}
              </div>
            );
          })}
        </div>
      </section>

      <section id="source" className="flex gap-1 scroll-mt-20">
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
    <div className="flex flex-col gap-2 items-center">
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
          <ArrowDownIcon size={15} className="text-grey" />

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
