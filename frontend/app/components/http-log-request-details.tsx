import {
  ChevronRightIcon,
  FilterIcon,
  SquareArrowOutUpRightIcon
} from "lucide-react";
import { useSearchParams } from "react-router";
import { CopyButton } from "~/components/copy-button";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
import { Button } from "~/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle
} from "~/components/ui/sheet";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { STANDARD_HTTP_STATUS_CODES } from "~/lib/constants";
import type { HttpLog } from "~/lib/queries";
import { cn } from "~/lib/utils";
import { formattedTime } from "~/utils";

type HttpLogRequestDetailsProps = {
  log?: HttpLog;
  open?: boolean;
  onClose?: () => void;
};

export function HttpLogRequestDetails({
  log,
  onClose,
  open = false
}: HttpLogRequestDetailsProps) {
  return (
    <Sheet
      open={open}
      onOpenChange={(open) => {
        if (!open) {
          onClose?.();
        }
      }}
    >
      <SheetContent
        side="right"
        className={cn(
          "z-99 border-border flex flex-col gap-4 overflow-y-auto",
          import.meta.env.DEV && "[&_[data-slot=close-btn]]:top-10"
        )}
      >
        {log && <LogRequestDetailsContent log={log} />}
      </SheetContent>
    </Sheet>
  );
}

function LogRequestDetailsContent({ log }: { log: HttpLog }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryParams = new URLSearchParams(log.request_query ?? "");
  const statusMessage = STANDARD_HTTP_STATUS_CODES[log.status];
  let duration = log.request_duration_ns / 1_000_000;
  let unit = "ms";

  if (duration > 1000) {
    duration = duration / 1_000;
    unit = "s";
  }

  return (
    <>
      <SheetHeader>
        <SheetTitle className="font-normal text-card-foreground mt-5 text-base text-start">
          <span className="border border-gray-600 bg-gray-600/10 px-2 py-1 border-opacity-60 rounded-md ">
            {log.request_method}
          </span>
          &nbsp;
          <span className="font-medium break-all">{log.request_path}</span>
        </SheetTitle>
      </SheetHeader>
      <hr className="border-border -mx-6" />
      <h3 className="font-medium">Request metadata:</h3>

      <dl className="flex flex-col gap-x-4 gap-y-2 items-center auto-rows-max">
        <div className="grid grid-cols-2 items-center gap-x-4 w-full">
          <dt className="text-grey  inline-flex items-center">ID</dt>
          <dd className="text-sm">{log.request_id}</dd>
        </div>

        <div className="grid grid-cols-2 items-center gap-x-4 w-full group">
          <dt className="text-grey inline-flex items-center">
            <span>Status code</span>

            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                    onClick={() => {
                      searchParams.set("status", log.status.toString());
                      searchParams.delete("request_id");
                      setSearchParams(searchParams, { replace: true });
                    }}
                  >
                    <FilterIcon size={15} />
                    <span className="sr-only">Add Filter</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Add Filter</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </dt>
          <dd
            className={cn("inline-flex items-center gap-1", {
              "text-blue-600": log.status.toString().startsWith("1"),
              "text-green-600": log.status.toString().startsWith("2"),
              "text-grey": log.status.toString().startsWith("3"),
              "text-yellow-600": log.status.toString().startsWith("4"),
              "text-red-600": log.status.toString().startsWith("5")
            })}
          >
            <span>
              {statusMessage ? `${log.status} ${statusMessage}` : log.status}
            </span>

            <a
              target="_blank"
              href={`https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/${log.status}`}
            >
              <span className="sr-only">Link to MDN</span>
              <SquareArrowOutUpRightIcon size={15} />
            </a>
          </dd>
        </div>

        <div className="grid grid-cols-2 items-center gap-x-4 w-full">
          <dt className="text-grey  inline-flex items-center">Date</dt>
          <dd className="text-sm">
            <time
              className="text-grey whitespace-nowrap"
              dateTime={new Date(log.time).toISOString()}
            >
              {formattedTime(log.time)}
            </time>
          </dd>
        </div>

        <div className="grid grid-cols-2 items-center gap-x-4 w-full">
          <dt className="text-grey  inline-flex items-center">Duration</dt>
          <dd className="text-sm">
            {Intl.NumberFormat("en-US", {
              maximumFractionDigits: 3
            }).format(duration)}
            <span className="text-grey">{unit}</span>
          </dd>
        </div>

        <div className="grid grid-cols-2 items-center gap-x-4 w-full">
          <dt className="text-grey  inline-flex items-center">Protocol</dt>
          <dd className="text-sm">{log.request_protocol}</dd>
        </div>

        <div className="grid grid-cols-2 items-center gap-x-4 w-full group">
          <dt className="text-grey inline-flex items-center">
            <span>Client IP</span>
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                    onClick={() => {
                      searchParams.set("request_ip", log.request_ip);
                      searchParams.delete("request_id");
                      setSearchParams(searchParams, { replace: true });
                    }}
                  >
                    <FilterIcon size={15} />
                    <span className="sr-only">Add Filter</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Add Filter</TooltipContent>
              </Tooltip>

              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <CopyButton label="Copy value" value={log.request_ip} />
                </TooltipTrigger>
                <TooltipContent>Copy value</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </dt>
          <dd className="text-sm break-all text-grey">{log.request_ip}</dd>
        </div>

        <div className="grid grid-cols-2 items-start gap-x-4 w-full group">
          <dt className="text-grey inline-flex items-center gap-1">
            <span>User Agent</span>
            <TooltipProvider>
              {log.request_user_agent && (
                <>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                        onClick={() => {
                          searchParams.set(
                            "request_user_agent",
                            log.request_user_agent!
                          );
                          searchParams.delete("request_id");
                          setSearchParams(searchParams, { replace: true });
                        }}
                      >
                        <FilterIcon size={15} />
                        <span className="sr-only">Add Filter</span>
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Add Filter</TooltipContent>
                  </Tooltip>

                  <Tooltip delayDuration={0}>
                    <TooltipTrigger asChild>
                      <CopyButton
                        label="Copy value"
                        value={log.request_user_agent}
                      />
                    </TooltipTrigger>
                    <TooltipContent>Copy value</TooltipContent>
                  </Tooltip>
                </>
              )}
            </TooltipProvider>
          </dt>
          <dd className="text-sm text-grey inline-flex h-full items-center break-all">
            {log.request_user_agent ?? <span className="font-mono">N/A</span>}
          </dd>
        </div>
      </dl>

      <hr className="border-border -mx-6" />

      <h3 className="font-medium">URL data:</h3>
      <dl className="flex flex-col gap-x-4 gap-y-2 items-center auto-rows-max">
        <div className="grid grid-cols-2 items-center gap-x-4 w-full group">
          <dt className="text-grey inline-flex items-center gap-1 group">
            <span>Host</span>
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                    onClick={() => {
                      searchParams.set("request_host", log.request_host);
                      searchParams.delete("request_id");
                      setSearchParams(searchParams, { replace: true });
                    }}
                  >
                    <FilterIcon size={15} />
                    <span className="sr-only">Add Filter</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Add Filter</TooltipContent>
              </Tooltip>

              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <CopyButton label="Copy value" value={log.request_host} />
                </TooltipTrigger>
                <TooltipContent>Copy value</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </dt>
          <dd className="text-sm">{log.request_host}</dd>
        </div>

        <div className="grid grid-cols-2 items-center gap-x-4 w-full">
          <dt className="text-grey inline-flex items-center gap-1 group">
            <span>Path</span>
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                    onClick={() => {
                      searchParams.set("request_path", log.request_path);
                      searchParams.delete("request_id");
                      setSearchParams(searchParams, { replace: true });
                    }}
                  >
                    <FilterIcon size={15} />
                    <span className="sr-only">Add Filter</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Add Filter</TooltipContent>
              </Tooltip>

              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <CopyButton label="Copy value" value={log.request_path} />
                </TooltipTrigger>
                <TooltipContent>Copy value</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </dt>
          <dd className="text-sm">
            <a
              href={`//${log.request_host}${log.request_path}`}
              target="_blank"
              className="text-link underline break-all"
            >
              {log.request_path}
            </a>
          </dd>
        </div>

        {log.request_query && (
          <div className="grid grid-cols-2 items-center gap-x-4 w-full border-b-0 border-border pb-2">
            <dt className="text-grey inline-flex items-center gap-1 group">
              <span>Query</span>
              <TooltipProvider>
                {log.request_query && (
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                        onClick={() => {
                          searchParams.set("request_query", log.request_query!);
                          searchParams.delete("request_id");
                          setSearchParams(searchParams, { replace: true });
                        }}
                      >
                        <FilterIcon size={15} />
                        <span className="sr-only">Add Filter</span>
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Add Filter</TooltipContent>
                  </Tooltip>
                )}

                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <CopyButton
                      label="Copy value"
                      value={`?${log.request_query}`}
                    />
                  </TooltipTrigger>
                  <TooltipContent>Copy value</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </dt>
            <dd className="text-sm">
              <span className="text-grey">{"?"}</span>
              {[...queryParams.entries()].map(([key, value], index) => (
                <span key={`${key}-${index}`}>
                  <span className="text-link">{key}</span>
                  {value && (
                    <>
                      <span className="text-grey">{"="}</span>
                      <span className="text-card-foreground break-all">
                        {value}
                      </span>
                    </>
                  )}
                  {index < queryParams.size - 1 && (
                    <span className="text-grey">{"&"}</span>
                  )}
                </span>
              ))}
            </dd>
          </div>
        )}
      </dl>

      <hr className="border-border -mx-6" />
      <Accordion type="single" collapsible defaultValue="request">
        <AccordionItem value="request" className="border-0">
          <AccordionTrigger className="gap-2 py-0 data-[state=open]:pb-4">
            <ChevronRightIcon className="h-4 w-4 shrink-0 transition-transform duration-200" />
            <h3>Response headers:</h3>
          </AccordionTrigger>
          <AccordionContent className="flex flex-col pb-0">
            <dl className="flex flex-col gap-0.5 text-base">
              {transformHeadersObjectToArray(log.response_headers).map(
                ([key, value], index) => (
                  <div className="inline gap-1 w-full" key={index}>
                    <dt className="text-link inline flex-none">{key}:</dt>
                    &nbsp;&nbsp;
                    <dd className="break-all inline text-grey">{value}</dd>
                  </div>
                )
              )}
            </dl>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
      <hr className="border-border -mx-6" />
      <Accordion type="single" collapsible defaultValue="response">
        <AccordionItem value="response" className="border-0">
          <AccordionTrigger className="gap-2 py-0 data-[state=open]:pb-4">
            <ChevronRightIcon className="h-4 w-4 shrink-0 transition-transform duration-200" />
            <h3>Request headers:</h3>
          </AccordionTrigger>
          <AccordionContent className="flex flex-col pb-0">
            <dl className="flex flex-col gap-0.5 text-base">
              {transformHeadersObjectToArray(log.request_headers).map(
                ([key, value], index) => (
                  <div className="inline gap-1 w-full" key={index}>
                    <dt className="text-link inline flex-none">{key}:</dt>
                    &nbsp;&nbsp;
                    <dd className="break-all inline text-grey">{value}</dd>
                  </div>
                )
              )}
            </dl>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
      <hr className="border-border -mx-6" />
    </>
  );
}

function transformHeadersObjectToArray(current: {
  [key: string]: string[];
}): Array<[string, string]> {
  const target: Array<[string, string]> = [];

  for (const key in current) {
    if (current.hasOwnProperty(key)) {
      current[key].forEach((value) => {
        target.push([key, value]);
      });
    }
  }

  return target;
}
