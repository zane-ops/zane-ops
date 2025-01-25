import hljs from "highlight.js/lib/core";
import json from "highlight.js/lib/languages/json";
import {
  BookmarkIcon,
  ChevronRightIcon,
  FilmIcon,
  GitCompareArrowsIcon,
  HashIcon,
  InfoIcon,
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
import { formatElapsedTime, formattedTime, pluralize } from "~/utils";
import { type Route } from "./+types/deployment-details";
import "highlight.js/styles/atom-one-dark.css";
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

  console.log({
    changes: deployment.changes
  });
  return (
    <div className="my-6 flex flex-col">
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

      <section id="source" className="flex gap-1 scroll-mt-20">
        <div className="w-16 hidden md:flex flex-col items-center">
          <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
            <GitCompareArrowsIcon size={15} className="flex-none text-grey" />
          </div>
          <div className="h-full border border-grey/50"></div>
        </div>

        <div className="w-full flex flex-col gap-5 pt-1 pb-8">
          <h2 className="text-lg text-grey">Changes</h2>
          {deployment.changes.length === 0 && (
            <div
              className={cn(
                "border-dashed border border-border rounded-md px-4 py-8 font-mono",
                "flex items-center justify-center text-foreground"
              )}
            >
              N/A
            </div>
          )}
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
