import { useQuery } from "@tanstack/react-query";
import hljs from "highlight.js/lib/core";
import json from "highlight.js/lib/languages/json";
import "highlight.js/styles/atom-one-dark.css";
import { DiffEditor } from "@monaco-editor/react";
import {
  ChevronRightIcon,
  ClockIcon,
  FileTextIcon,
  FilmIcon,
  GitCompareArrowsIcon,
  HashIcon,
  InfoIcon,
  KeyRoundIcon,
  LoaderIcon,
  type LucideIcon,
  MessageCircleCodeIcon,
  TrendingUpIcon
} from "lucide-react";
import * as React from "react";
import { Link, href } from "react-router";
import { EnvVariableChangeItem } from "~/components/change-fields";
import { CopyButton } from "~/components/copy-button";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
import { DiffCodeEditor } from "~/components/ui/code-editor";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { composeStackQueries } from "~/lib/queries";
import { cn } from "~/lib/utils";
import { capitalizeText, formatElapsedTime, formattedTime } from "~/utils";
import type { Route } from "./+types/compose-stack-deployment-details";

hljs.registerLanguage("json", json);

export default function ComposeStackDeploymentDetailsPage({
  params,
  matches: {
    2: { loaderData }
  }
}: Route.ComponentProps) {
  const { data: deployment } = useQuery({
    ...composeStackQueries.singleDeployment({
      project_slug: params.projectSlug,
      stack_slug: params.composeStackSlug,
      env_slug: params.envSlug,
      deployment_hash: params.deploymentHash
    }),
    initialData: loaderData.deployment
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
    JSON.stringify(deployment.stack_snapshot, null, 2),
    { language: "json" }
  ).value;

  const deploymentChanges = Object.groupBy(
    deployment.changes,
    ({ field }) => field
  );

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

  const [hasCopied, startTransition] = React.useTransition();

  const IconFieldMap: Record<
    (typeof deployment.changes)[number]["field"],
    LucideIcon
  > = {
    compose_content: FileTextIcon,
    env_overrides: KeyRoundIcon
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
                    to={href(
                      "/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug/deployments/:deploymentHash",
                      params
                    )}
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

            <div className="flex flex-col items-start gap-2">
              <dt className="flex gap-1 items-center text-grey">
                <MessageCircleCodeIcon size={15} />
                <span>Full commit message:</span>
              </dt>
              <dd className="w-full">
                <pre className="font-mono bg-muted/25 dark:bg-card p-2 rounded-md text-sm break-all w-full">
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
            const fieldNames: Record<
              (typeof deployment.changes)[number]["field"],
              string
            > = {
              compose_content: "Compose stack file contents",
              env_overrides: "Environment overrides"
            };

            return (
              <div key={field} className="flex flex-col gap-1.5 flex-1">
                <h3 className="text-lg flex gap-2 items-center border-b py-2 border-border">
                  <Icon size={15} className="flex-none text-grey" />
                  <span>{fieldNames[field]}</span>
                </h3>
                <div className="pl-4 py-2 flex flex-col gap-2">
                  {field === "env_overrides" &&
                    changes.map((change) => (
                      <React.Fragment key={change.id}>
                        <EnvVariableChangeItem
                          change={change}
                          key={change.id}
                        />
                        <hr className="border border-dashed border-border" />
                      </React.Fragment>
                    ))}
                  {field === "compose_content" && (
                    <DiffCodeEditor
                      original={changes[0].old_value as string}
                      modified={changes[0].new_value as string}
                      readOnly
                      containerClassName={cn(
                        "w-full h-100",
                        "w-[80dvw] sm:w-[88dvw] md:w-[82dvw] lg:w-[73dvw] xl:w-[882px]"
                      )}
                      language="yaml"
                    />
                  )}
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
            The status of the compose stack at the time of the deployment.
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
                        <CopyButton
                          label="Copy value"
                          value={JSON.stringify(
                            deployment.stack_snapshot,
                            null,
                            2
                          )}
                          className="!opacity-100 absolute top-2 right-2"
                        />
                      </TooltipTrigger>
                      <TooltipContent>Copy value</TooltipContent>
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
