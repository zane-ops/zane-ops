import { useQuery } from "@tanstack/react-query";
import { type VariantProps, cva } from "class-variance-authority";
import { format } from "date-fns";
import {
  Ban,
  CalendarIcon,
  CheckIcon,
  ChevronDownIcon,
  EllipsisVertical,
  Eye,
  HashIcon,
  LoaderIcon,
  Redo2,
  ScanTextIcon,
  TimerIcon,
  Undo2Icon,
  XIcon
} from "lucide-react";
import * as React from "react";
import type { DateRange } from "react-day-picker";
import { Link, useFetcher, useNavigate, useSearchParams } from "react-router";
import type { ComposeStackDeployment } from "~/api/types";
import { Code } from "~/components/code";
import { Pagination } from "~/components/pagination";
import { Button } from "~/components/ui/button";
import { Calendar } from "~/components/ui/calendar";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList
} from "~/components/ui/command";
import {
  Menubar,
  MenubarContent,
  MenubarContentItem,
  MenubarMenu,
  MenubarTrigger
} from "~/components/ui/menubar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from "~/components/ui/popover";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { composeStackQueries, stackDeploymentListFilters } from "~/lib/queries";
import { cn } from "~/lib/utils";
import { queryClient } from "~/root";
import {
  capitalizeText,
  formatElapsedTime,
  formattedTime,
  mergeTimeAgoFormatterAndFormattedDate
} from "~/utils";
import type { Route } from "./+types/compose-stack-deployment-list";

export async function clientLoader({
  request,
  params
}: Route.ClientLoaderArgs) {
  const searchParams = new URL(request.url).searchParams;
  const search = stackDeploymentListFilters.parse(searchParams);
  const filters = {
    page: search.page ?? 1,
    per_page: search.per_page ?? 10,
    status: search.status,
    queued_at_after: search.queued_at_after,
    queued_at_before: search.queued_at_before
  };

  const deploymentList = await queryClient.ensureQueryData(
    composeStackQueries.deploymentList({
      project_slug: params.projectSlug,
      env_slug: params.envSlug,
      stack_slug: params.composeStackSlug,
      filters
    })
  );

  return { deploymentList };
}

export default function ComposeStackDeploymentListPage({
  loaderData,
  params
}: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const search = stackDeploymentListFilters.parse(searchParams);
  const filters = {
    page: search.page ?? 1,
    per_page: search.per_page ?? 10,
    status: search.status,
    queued_at_after: search.queued_at_after,
    queued_at_before: search.queued_at_before
  };
  const {
    data: { results: deploymentList, count: totalDeployments }
  } = useQuery({
    ...composeStackQueries.deploymentList({
      project_slug: params.projectSlug,
      env_slug: params.envSlug,
      stack_slug: params.composeStackSlug,
      filters
    }),
    initialData: loaderData.deploymentList
  });

  const date: DateRange = {
    from: filters.queued_at_after,
    to: filters.queued_at_before
  };

  const noFilters =
    !search.per_page &&
    !search.queued_at_after &&
    !search.queued_at_before &&
    (search.status ?? []).length === 0;

  // all deployments that match these filters are considered `new`
  const newDeploymentsStatuses: Array<ComposeStackDeployment["status"]> = [
    "QUEUED",
    "DEPLOYING"
  ];

  const newDeployments = deploymentList.filter((dpl) =>
    newDeploymentsStatuses.includes(dpl.status)
  );

  const previousDeployments = deploymentList.filter(
    (dpl) => !newDeploymentsStatuses.includes(dpl.status)
  );

  const noDeploymentsYet = deploymentList.length === 0 && noFilters;
  const noResultsFound = !noFilters && deploymentList.length === 0;

  const totalPages = Math.ceil(totalDeployments / filters.per_page);

  return noDeploymentsYet ? (
    <div className="flex justify-center items-center">
      <div className="flex gap-2 flex-col items-center mt-40">
        <h1 className="text-2xl font-bold">No Deployments made yet</h1>
        <h2 className="text-lg">Your stack is offline</h2>
        {/* <DeployForm service_type={service.type} /> */}
      </div>
    </div>
  ) : (
    <section className="flex flex-col gap-6 mt-8">
      <div className="flex flex-col md:flex-row gap-2">
        <Popover>
          <PopoverTrigger asChild>
            <Button
              id="date"
              variant="outline"
              className={cn(
                "w-full md:w-[300px] justify-start text-left font-normal",
                !date && "text-muted-foreground"
              )}
            >
              <CalendarIcon className="mr-2 h-4 w-4" />
              {date?.from ? (
                date.to ? (
                  <>
                    {format(date.from, "LLL dd, y")} -{" "}
                    {format(date.to, "LLL dd, y")}
                  </>
                ) : (
                  format(date.from, "LLL dd, y")
                )
              ) : (
                <span>Pick a date</span>
              )}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0" align="start">
            <Calendar
              initialFocus
              mode="range"
              defaultMonth={date?.from}
              selected={date}
              onSelect={(range) => {
                if (range?.from) {
                  searchParams.set("queued_at_after", range.from.toISOString());
                }
                if (range?.to) {
                  searchParams.set("queued_at_before", range.to.toISOString());
                }

                setSearchParams(searchParams, { replace: true });
              }}
              numberOfMonths={2}
            />
          </PopoverContent>
        </Popover>
        <div className="w-full md:w-fit">
          <DeploymentStatusesMultiSelect
            options={["QUEUED", "DEPLOYING", "FINISHED", "FAILED", "CANCELLED"]}
            onValueChange={(values) => {
              searchParams.delete("status");
              values.forEach((value) => {
                searchParams.append("status", value);
              });
              setSearchParams(searchParams, { replace: true });
            }}
            value={filters.status ?? []}
            placeholder="Status"
            variant="inverted"
            animation={2}
            maxCount={3}
          />
        </div>

        {!noFilters && (
          <Button variant="outline" asChild>
            <Link
              to="./"
              replace
              className="inline-flex gap-1 w-full md:w-min justify-start"
            >
              <XIcon size={15} />
              <span>Reset filters</span>
            </Link>
          </Button>
        )}
      </div>
      <div className="flex flex-col gap-4">
        {deploymentList.map((dpl) => (
          <ComposeStackDeploymentCard
            key={dpl.hash}
            hash={dpl.hash}
            queued_at={new Date(dpl.queued_at)}
            started_at={dpl.started_at ? new Date(dpl.started_at) : null}
            finished_at={dpl.finished_at ? new Date(dpl.finished_at) : null}
            status={dpl.status}
            redeploy_hash={dpl.redeploy_hash}
            commit_message={dpl.commit_message}
          />
        ))}
      </div>
      <div className="my-4 block">
        {!noDeploymentsYet && !noResultsFound && totalDeployments > 10 && (
          <Pagination
            totalPages={totalPages}
            currentPage={filters.page}
            perPage={filters.per_page}
            onChangePage={(newPage) => {
              searchParams.set("page", newPage.toString());
              setSearchParams(searchParams, {
                replace: true
              });
            }}
            onChangePerPage={(newPerPage) => {
              searchParams.set("page", "1");
              searchParams.set("per_page", newPerPage.toString());
              setSearchParams(searchParams, {
                replace: true
              });
            }}
          />
        )}
      </div>
    </section>
  );
}

export type ComposeStackDeploymentCardProps = Pick<
  ComposeStackDeployment,
  "status" | "hash" | "redeploy_hash" | "commit_message"
> & {
  queued_at: Date;
  started_at: Date | null;
  finished_at: Date | null;
};

export function ComposeStackDeploymentCard({
  started_at,
  finished_at,
  status,
  queued_at,
  hash,
  redeploy_hash,
  commit_message
}: ComposeStackDeploymentCardProps) {
  const now = new Date();

  const [timeElapsed, setTimeElapsed] = React.useState(
    started_at ? Math.ceil((now.getTime() - started_at.getTime()) / 1000) : 0
  );
  const navigate = useNavigate();

  React.useEffect(() => {
    if (started_at && !finished_at) {
      const timer = setInterval(() => {
        setTimeElapsed(() =>
          Math.ceil((new Date().getTime() - started_at.getTime()) / 1000)
        );
      }, 1000);

      return () => clearInterval(timer);
    }
  }, [started_at, finished_at]);

  // all deployments statuse that match these filters can be cancelled
  const cancellableDeploymentsStatuses: Array<typeof status> = [
    "QUEUED",
    "DEPLOYING"
  ];

  const runningDeploymentsStatuses: Array<typeof status> = [
    "QUEUED",
    "DEPLOYING"
  ];

  const isCancellable = cancellableDeploymentsStatuses.includes(status);
  const isRedeployable =
    finished_at || !runningDeploymentsStatuses.includes(status);

  const redeployFetcher = useFetcher();
  const cancelFetcher = useFetcher();

  return (
    <div
      className={cn(
        "flex flex-col md:flex-row items-start gap-4 md:gap-0 border group  px-3 py-4 rounded-md justify-between md:items-center relative",
        {
          "border-blue-600 bg-blue-600/10": status === "DEPLOYING",
          "border-green-600 bg-green-600/10": status === "FINISHED",
          "border-red-600 bg-red-600/10": status === "FAILED",
          "border-gray-600 bg-gray-600/10":
            status === "CANCELLED" || status === "QUEUED"
        }
      )}
    >
      <div className="flex flex-col md:flex-row gap-4 md:gap-0">
        {/* Status name */}
        <div className="w-[160px]">
          <h3 className="flex items-center gap-1 capitalize">
            <span
              className={cn("text-lg", {
                "text-blue-500": status === "DEPLOYING",
                "text-green-500": status === "FINISHED",
                "text-red-500": status === "FAILED",
                "text-gray-500 dark:text-gray-400": status === "QUEUED",
                "text-card-foreground rounded-md bg-gray-400/40 dark:bg-gray-500/60 px-1":
                  status === "CANCELLED"
              })}
            >
              {capitalizeText(status)}
            </span>
            {Boolean(started_at && !finished_at) && (
              <LoaderIcon className="animate-spin" size={15} />
            )}
          </h3>
          <TooltipProvider>
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <time
                  dateTime={queued_at.toISOString()}
                  className="text-sm relative z-10 text-gray-500/80 dark:text-gray-400 text-nowrap"
                >
                  {mergeTimeAgoFormatterAndFormattedDate(queued_at)}
                </time>
              </TooltipTrigger>
              <TooltipContent className="max-w-64 text-balance">
                {formattedTime(queued_at)}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>

        {/* Commit message & timer */}
        <div className="flex flex-col items-start gap-1">
          <h3 className="inline-flex flex-wrap gap-0.5">
            <Link
              prefetch="viewport"
              to={`./${hash}`}
              className="whitespace-nowrap after:absolute after:inset-0 overflow-x-hidden text-ellipsis max-w-[300px] sm:max-w-[500px] lg:max-w-[600px] xl:max-w-[800px]"
            >
              {capitalizeText(commit_message.split("\n")[0])}
            </Link>
            &nbsp;
            {redeploy_hash && (
              <small>
                <Code className="whitespace-nowrap inline-flex items-center gap-1">
                  <Undo2Icon size={12} className="flex-none" />
                  <span>Redeploy of {redeploy_hash}</span>
                </Code>
              </small>
            )}
          </h3>
          <div className="flex relative z-10 text-gray-500/80 dark:text-gray-400 gap-2.5 text-sm w-full items-start flex-wrap md:items-center">
            <div className="gap-0.5 inline-flex items-center">
              <TimerIcon size={15} className="flex-none" />
              {started_at && !finished_at ? (
                <span>{formatElapsedTime(timeElapsed)}</span>
              ) : started_at && finished_at ? (
                <span>
                  {formatElapsedTime(
                    Math.round(
                      (new Date(finished_at).getTime() -
                        new Date(started_at).getTime()) /
                        1000
                    )
                  )}
                </span>
              ) : (
                <span>-</span>
              )}
            </div>

            <div className="inline-flex items-center gap-0.5 right-1">
              <HashIcon size={15} className="flex-none" />
              <span>{hash}</span>
            </div>
          </div>
        </div>
      </div>

      {/* View logs button & triple dot */}
      <div className="flex items-center gap-2 absolute right-4 z-10 md:relative md:right-auto">
        <Button
          asChild
          variant="ghost"
          className={cn(
            "border hover:bg-inherit focus:opacity-100 hidden lg:inline-flex",
            {
              "border-blue-600": status === "DEPLOYING",
              "border-green-600": status === "FINISHED",
              "border-red-600": status === "FAILED",
              "border-gray-600 md:opacity-0 group-hover:opacity-100 transition-opacity ease-in duration-150":
                status === "CANCELLED" || status === "QUEUED"
            }
          )}
        >
          <Link to={`./${hash}`}>View logs</Link>
        </Button>

        {isRedeployable && (
          <redeployFetcher.Form
            method="post"
            action={`./${hash}/redeploy`}
            id={`redeploy-${hash}-form`}
            className="hidden"
          />
        )}
        {isCancellable && (
          <cancelFetcher.Form
            method="post"
            action={`./${hash}/cancel`}
            id={`cancel-${hash}-form`}
            className="hidden"
          />
        )}

        <Menubar className="border-none h-auto w-fit">
          <MenubarMenu>
            <MenubarTrigger
              className="flex justify-center items-center gap-2"
              asChild
            >
              <Button variant="ghost" className="px-1.5 py-1 hover:bg-inherit">
                <EllipsisVertical className="flex-none" />
              </Button>
            </MenubarTrigger>
            <MenubarContent
              side="bottom"
              align="center"
              className="border min-w-0 mx-9 border-border"
            >
              <MenubarContentItem
                icon={Eye}
                text="Details"
                onClick={() => navigate(`./${hash}/details`)}
              />
              <MenubarContentItem
                icon={ScanTextIcon}
                text="View logs"
                onClick={() => navigate(`./${hash}`)}
              />

              {isRedeployable && (
                <button
                  form={`redeploy-${hash}-form`}
                  className="w-full"
                  disabled={redeployFetcher.state !== "idle"}
                  onClick={(e) => {
                    e.currentTarget.form?.requestSubmit();
                  }}
                >
                  <MenubarContentItem icon={Redo2} text="Redeploy" />
                </button>
              )}
              {isCancellable && (
                <button
                  form={`cancel-${hash}-form`}
                  className="w-full"
                  onClick={(e) => {
                    e.currentTarget.form?.requestSubmit();
                  }}
                  disabled={cancelFetcher.state !== "idle"}
                >
                  <MenubarContentItem
                    className="text-red-500"
                    icon={Ban}
                    text="Cancel"
                  />
                </button>
              )}
            </MenubarContent>
          </MenubarMenu>
        </Menubar>
      </div>
    </div>
  );
}

/**
 * Variants for the multi-select component to handle different styles.
 * Uses class-variance-authority (cva) to define different styles based on "variant" prop.
 */
const multiSelectVariants = cva(
  "m-1 transition ease-in-out delay-150 hover:-translate-y-1 hover:scale-110 duration-300",
  {
    variants: {
      variant: {
        default:
          "border-foreground/10 text-foreground bg-card hover:bg-card/80",
        secondary:
          "border-foreground/10 bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive:
          "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",
        inverted: "inverted"
      }
    },
    defaultVariants: {
      variant: "default"
    }
  }
);

interface MultiSelectProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof multiSelectVariants> {
  /**
   * An array of option objects to be displayed in the multi-select component.
   * Each option object has a label, value, and an optional icon.
   */
  options: string[];

  /**
   * Callback function triggered when the selected values change.
   * Receives an array of the new selected values.
   */
  onValueChange: (value: string[]) => void;

  /**
   * Placeholder text to be displayed when no values are selected.
   * Optional, defaults to "Select options".
   */
  placeholder?: string;

  /**
   * Animation duration in seconds for the visual effects (e.g., bouncing badges).
   * Optional, defaults to 0 (no animation).
   */
  animation?: number;

  /**
   * Maximum number of items to display. Extra selected items will be summarized.
   * Optional, defaults to 3.
   */
  maxCount?: number;

  /**
   * The modality of the popover. When set to true, interaction with outside elements
   * will be disabled and only popover content will be visible to screen readers.
   * Optional, defaults to false.
   */
  modalPopover?: boolean;

  /**
   * If true, renders the multi-select component as a child of another component.
   * Optional, defaults to false.
   */
  asChild?: boolean;

  /**
   * Additional class names to apply custom styles to the multi-select component.
   * Optional, can be used to add custom styles.
   */
  className?: string;
  value: string[];
}
const DeploymentStatusesMultiSelect = ({
  ref,
  options,
  onValueChange,
  variant,
  value = [],
  placeholder = "Select options",
  animation = 0,
  maxCount = 3,
  modalPopover = false,
  asChild = false,
  className,
  ...props
}: MultiSelectProps & {
  ref?: React.RefObject<HTMLButtonElement>;
}) => {
  const [isPopoverOpen, setIsPopoverOpen] = React.useState(false);

  const handleInputKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      setIsPopoverOpen(true);
    }
  };

  const toggleOption = (option: string) => {
    const newSelectedValues = value.includes(option)
      ? value.filter((v) => v !== option)
      : [...value, option];
    onValueChange(newSelectedValues);
  };

  const handleClear = () => {
    onValueChange([]);
  };

  const handleTogglePopover = () => {
    setIsPopoverOpen((prev) => !prev);
  };

  const toggleAll = () => {
    if (value.length === options.length) {
      handleClear();
    } else {
      onValueChange(options);
    }
  };

  return (
    <Popover
      open={isPopoverOpen}
      onOpenChange={setIsPopoverOpen}
      modal={modalPopover}
    >
      <PopoverTrigger asChild>
        <Button
          ref={ref}
          {...props}
          onClick={handleTogglePopover}
          className={cn(
            "flex w-full p-1 rounded-md border border-border min-h-10 h-auto items-center justify-between bg-inherit hover:bg-inherit",
            className
          )}
        >
          <div className="flex items-center justify-between w-full mx-auto">
            <div className="flex items-center">
              <div className="mx-2 flex items-center w-12 overflow-visible">
                <div
                  className={cn(
                    "w-3 flex-none h-3 border border-border rounded-full",
                    {
                      "bg-gray-400": value.includes("QUEUED"),
                      "bg-background": !value.includes("QUEUED")
                    }
                  )}
                />

                <div
                  className={cn(
                    "w-3 flex-none h-3 border relative -left-1 border-border rounded-full",
                    {
                      "bg-gray-400": value.includes("CANCELLED"),
                      "bg-background": !value.includes("CANCELLED")
                    }
                  )}
                />

                <div
                  className={cn(
                    "w-3 flex-none relative -left-2 h-3 border border-border rounded-full",
                    {
                      "bg-red-400": value.includes("FAILED"),
                      "bg-background": !value.includes("FAILED")
                    }
                  )}
                />

                <div
                  className={cn(
                    "w-3 flex-none h-3 relative -left-3 border border-border rounded-full",
                    {
                      "bg-green-400": value.includes("FINISHED"),
                      "bg-background": !value.includes("FINISHED")
                    }
                  )}
                />

                <div
                  className={cn(
                    "w-3 flex-none h-3 border relative -left-4 border-border rounded-full",
                    {
                      "bg-blue-400": value.includes("DEPLOYING"),
                      "bg-background": !value.includes("DEPLOYING")
                    }
                  )}
                />
              </div>

              <span className="text-sm text-muted-foreground">
                {placeholder}
              </span>
            </div>
            <ChevronDownIcon className="h-4 cursor-pointer text-muted-foreground mx-2" />
          </div>
        </Button>
      </PopoverTrigger>
      <PopoverContent
        className="w-auto p-0"
        align="start"
        onEscapeKeyDown={() => setIsPopoverOpen(false)}
      >
        <Command>
          <CommandInput
            placeholder="Filter Statuses..."
            onKeyDown={handleInputKeyDown}
          />
          <CommandList>
            <CommandEmpty>No results found.</CommandEmpty>
            <CommandGroup>
              <CommandItem
                key="SELECT_ALL"
                onSelect={toggleAll}
                className="cursor-pointer flex gap-0.5"
              >
                <div
                  className={cn(
                    "mr-2 flex h-4 w-4 items-center justify-center rounded-sm border border-primary",
                    value.length === options.length
                      ? "bg-primary text-primary-foreground"
                      : "opacity-50 [&_svg]:invisible"
                  )}
                >
                  <CheckIcon className="h-4 w-4" />
                </div>

                <div className="flex items-center justify-between w-full">
                  <span>(Select all)</span>
                </div>
              </CommandItem>
              {options.map((option) => {
                const isSelected = value.includes(option);
                return (
                  <CommandItem
                    key={option}
                    onSelect={() => toggleOption(option)}
                    className="cursor-pointer flex gap-0.5"
                  >
                    <div
                      className={cn(
                        "mr-2 flex h-4 w-4 items-center justify-center rounded-sm border border-primary",
                        isSelected
                          ? "bg-primary text-primary-foreground"
                          : "opacity-50 [&_svg]:invisible"
                      )}
                    >
                      <CheckIcon className="h-4 w-4" />
                    </div>
                    <div className="flex items-center justify-between w-full">
                      <span>{option}</span>

                      <div
                        className={cn(
                          "relative rounded-full bg-green-400 w-2.5 h-2.5",
                          {
                            "bg-blue-400": option === "DEPLOYING",
                            "bg-green-600": option === "FINISHED",
                            "bg-red-400": option === "FAILED",
                            "bg-gray-400":
                              option === "CANCELLED" || option === "QUEUED"
                          }
                        )}
                      ></div>
                    </div>
                  </CommandItem>
                );
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
};
