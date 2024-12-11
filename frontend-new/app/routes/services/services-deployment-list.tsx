import { useQuery } from "@tanstack/react-query";
import { type VariantProps, cva } from "class-variance-authority";
import { format } from "date-fns";
import { CalendarIcon, CheckIcon, ChevronDown, LoaderIcon } from "lucide-react";
import * as React from "react";
import { type DateRange } from "react-day-picker";
import { Link, useFetcher, useSearchParams } from "react-router";
import type { Writeable } from "zod";
import { DockerDeploymentCard } from "~/components/deployment-cards";
import { Pagination } from "~/components/pagination";
import { Button, SubmitButton } from "~/components/ui/button";
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
  Popover,
  PopoverContent,
  PopoverTrigger
} from "~/components/ui/popover";
import { DEPLOYMENT_STATUSES } from "~/lib/constants";
import { serviceDeploymentListFilters, serviceQueries } from "~/lib/queries";
import { cn } from "~/lib/utils";
import { queryClient } from "~/root";
import { type Route } from "./+types/services-deployment-list";

export async function clientLoader({
  params: { projectSlug: project_slug, serviceSlug: service_slug },
  request
}: Route.ClientLoaderArgs) {
  const searchParams = new URL(request.url).searchParams;
  const search = serviceDeploymentListFilters.parse(searchParams);
  const filters = {
    page: search.page ?? 1,
    per_page: search.per_page ?? 10,
    status:
      search.status ??
      (DEPLOYMENT_STATUSES as Writeable<typeof DEPLOYMENT_STATUSES>),
    queued_at_after: search.queued_at_after,
    queued_at_before: search.queued_at_before
  };

  const deploymentList = await queryClient.ensureQueryData(
    serviceQueries.deploymentList({ project_slug, service_slug, filters })
  );

  return { deploymentList };
}

function DeployForm() {
  const fetcher = useFetcher();
  const isDeploying = fetcher.state !== "idle";
  return (
    <fetcher.Form method="post" action="./deploy-service">
      <SubmitButton isPending={isDeploying}>
        {isDeploying ? (
          <>
            <span>Deploying</span>
            <LoaderIcon className="animate-spin" size={15} />
          </>
        ) : (
          "Deploy now"
        )}
      </SubmitButton>
    </fetcher.Form>
  );
}

export default function DeploymentListPage({
  params: { projectSlug: project_slug, serviceSlug: service_slug },
  loaderData
}: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const search = serviceDeploymentListFilters.parse(searchParams);

  const filters = {
    page: search.page ?? 1,
    per_page: search.per_page ?? 10,
    status:
      search.status ??
      (DEPLOYMENT_STATUSES as Writeable<typeof DEPLOYMENT_STATUSES>),
    queued_at_after: search.queued_at_after,
    queued_at_before: search.queued_at_before
  };

  const {
    data: { results: deploymentList, count: totalDeployments }
  } = useQuery({
    ...serviceQueries.deploymentList({ project_slug, service_slug, filters }),
    initialData: loaderData.deploymentList
  });

  const date: DateRange = {
    from: filters.queued_at_after,
    to: filters.queued_at_before
  };

  const noFilters =
    !search.page &&
    !search.per_page &&
    !search.queued_at_after &&
    !search.queued_at_before &&
    (search.status ?? []).length === 0;

  const currentProductionDeployment = deploymentList.find(
    (dpl) => dpl.is_current_production
  );

  // all deployments that match these filters are considered `new`
  const newDeploymentsStatuses: Array<(typeof DEPLOYMENT_STATUSES)[number]> = [
    "QUEUED",
    "PREPARING",
    "STARTING",
    "RESTARTING",
    "CANCELLING"
  ];

  const newDeployments = deploymentList.filter(
    (dpl) =>
      dpl.hash !== currentProductionDeployment?.hash &&
      newDeploymentsStatuses.includes(dpl.status)
  );

  const previousDeployments = deploymentList.filter(
    (dpl) =>
      dpl.hash !== currentProductionDeployment?.hash &&
      !newDeploymentsStatuses.includes(dpl.status)
  );

  const noDeploymentsYet = deploymentList.length === 0 && noFilters;
  const noResultsFound: boolean = !noFilters && deploymentList.length === 0;

  const totalPages = Math.ceil(totalDeployments / filters.per_page);

  return (
    <>
      {noDeploymentsYet ? (
        <div className="flex justify-center items-center">
          <div className=" flex gap-1 flex-col items-center mt-40">
            <h1 className="text-2xl font-bold">No Deployments made yet</h1>
            <h2 className="text-lg">Your service is offline</h2>
            <DeployForm />
          </div>
        </div>
      ) : (
        <>
          <div className="flex mt-8 gap-2">
            <Popover>
              <PopoverTrigger asChild>
                <Button
                  id="date"
                  variant={"outline"}
                  className={cn(
                    "w-[300px] justify-start text-left font-normal",
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
                      searchParams.set(
                        "queued_at_after",
                        range.from.toISOString()
                      );
                    }
                    if (range?.to) {
                      searchParams.set(
                        "queued_at_before",
                        range.to.toISOString()
                      );
                    }

                    setSearchParams(searchParams, { replace: true });
                  }}
                  numberOfMonths={2}
                />
              </PopoverContent>
            </Popover>
            <div className="w-fit">
              <DeploymentStatusesMultiSelect
                options={DEPLOYMENT_STATUSES as unknown as string[]}
                onValueChange={(values) => {
                  searchParams.delete("status");
                  values.forEach((value) => {
                    searchParams.append("status", value);
                  });
                  setSearchParams(searchParams, { replace: true });
                }}
                value={filters.status}
                placeholder="Status"
                variant="inverted"
                animation={2}
                maxCount={3}
              />
            </div>
          </div>
          <div className="flex flex-col gap-4 mt-6">
            {noResultsFound ? (
              <div className="flex flex-col gap-2 items-center my-10">
                <h2 className="text-2xl font-medium">
                  No deployments match the filter criteria
                </h2>
                <h3 className="text-lg text-gray-500">
                  Change or clear the filters to view deployments.
                </h3>
                <Button asChild variant="outline">
                  <Link to=".">Clear filters</Link>
                </Button>
              </div>
            ) : (
              <>
                {newDeployments.length > 0 && (
                  <section className="flex flex-col gap-2">
                    <h2 className="text-gray-400 text-sm">New</h2>
                    <ul className="flex flex-col gap-4">
                      {newDeployments.map((deployment) => (
                        <li key={deployment.hash}>
                          <DockerDeploymentCard
                            commit_message={deployment.commit_message}
                            hash={deployment.hash}
                            status={deployment.status}
                            redeploy_hash={deployment.redeploy_hash}
                            image={deployment.service_snapshot.image}
                            queued_at={new Date(deployment.queued_at)}
                            started_at={
                              deployment.started_at
                                ? new Date(deployment.started_at)
                                : undefined
                            }
                            finished_at={
                              deployment.finished_at
                                ? new Date(deployment.finished_at)
                                : undefined
                            }
                            service_slug={service_slug}
                            project_slug={project_slug}
                          />
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
                {currentProductionDeployment && (
                  <section className="flex flex-col gap-2">
                    <h2 className="text-gray-400 text-sm">Current</h2>
                    <DockerDeploymentCard
                      commit_message={
                        currentProductionDeployment.commit_message
                      }
                      redeploy_hash={currentProductionDeployment.redeploy_hash}
                      hash={currentProductionDeployment.hash}
                      status={currentProductionDeployment.status}
                      image={currentProductionDeployment.service_snapshot.image}
                      queued_at={
                        new Date(currentProductionDeployment.queued_at)
                      }
                      started_at={
                        currentProductionDeployment.started_at
                          ? new Date(currentProductionDeployment.started_at)
                          : undefined
                      }
                      finished_at={
                        currentProductionDeployment.finished_at
                          ? new Date(currentProductionDeployment.finished_at)
                          : undefined
                      }
                      is_current_production
                      service_slug={service_slug}
                      project_slug={project_slug}
                    />
                  </section>
                )}
                {previousDeployments.length > 0 && (
                  <section className="flex flex-col gap-2">
                    <h2 className="text-gray-400 text-sm">Previous</h2>
                    <ul className="flex flex-col gap-4">
                      {previousDeployments.map((deployment) => (
                        <li key={deployment.hash}>
                          <DockerDeploymentCard
                            commit_message={deployment.commit_message}
                            hash={deployment.hash}
                            status={deployment.status}
                            image={deployment.service_snapshot.image}
                            queued_at={new Date(deployment.queued_at)}
                            redeploy_hash={deployment.redeploy_hash}
                            started_at={
                              deployment.started_at
                                ? new Date(deployment.started_at)
                                : undefined
                            }
                            finished_at={
                              deployment.finished_at
                                ? new Date(deployment.finished_at)
                                : undefined
                            }
                            service_slug={service_slug}
                            project_slug={project_slug}
                          />
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
              </>
            )}
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
        </>
      )}
    </>
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
              <div className="mx-2 flex items-center w-24 overflow-visible">
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
                    "w-3 flex-none h-3 border relative -left-1 border-border rounded-full",
                    {
                      "bg-blue-400": value.includes("CANCELLING"),
                      "bg-background": !value.includes("CANCELLING")
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
                      "bg-blue-400": value.includes("PREPARING"),
                      "bg-background": !value.includes("PREPARING")
                    }
                  )}
                />

                <div
                  className={cn(
                    "w-3 flex-none h-3 relative -left-4 border border-border rounded-full",
                    {
                      "bg-green-400": value.includes("HEALTHY"),
                      "bg-background": !value.includes("HEALTHY")
                    }
                  )}
                />

                <div
                  className={cn(
                    "w-3 flex-none h-3 border relative -left-5 border-border rounded-full",
                    {
                      "bg-red-400": value.includes("UNHEALTHY"),
                      "bg-background": !value.includes("UNHEALTHY")
                    }
                  )}
                />

                <div
                  className={cn(
                    "w-3 flex-none h-3 border relative -left-6 border-border rounded-full",
                    {
                      "bg-blue-400": value.includes("STARTING"),
                      "bg-background": !value.includes("STARTING")
                    }
                  )}
                />

                <div
                  className={cn(
                    "w-3 flex-none h-3 border relative -left-7 border-border rounded-full",
                    {
                      "bg-blue-400": value.includes("RESTARTING"),
                      "bg-background": !value.includes("RESTARTING")
                    }
                  )}
                />

                <div
                  className={cn(
                    "w-3 flex-none h-3 border relative -left-8 border-border rounded-full",
                    {
                      "bg-gray-400": value.includes("REMOVED"),
                      "bg-background": !value.includes("REMOVED")
                    }
                  )}
                />

                <div
                  className={cn(
                    "w-3 flex-none h-3 border relative -left-9 border-border rounded-full",
                    {
                      "bg-orange-400": value.includes("SLEEPING"),
                      "bg-background": !value.includes("SLEEPING")
                    }
                  )}
                />
              </div>

              <span className="text-sm text-muted-foreground">
                {placeholder}
              </span>
            </div>
            <ChevronDown className="h-4 cursor-pointer text-muted-foreground mx-2" />
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
                            "bg-blue-400":
                              option === "STARTING" ||
                              option === "RESTARTING" ||
                              option === "CANCELLING" ||
                              option === "PREPARING",
                            "bg-green-600": option === "HEALTHY",
                            "bg-red-400":
                              option === "UNHEALTHY" || option === "FAILED",
                            "bg-gray-400":
                              option === "REMOVED" ||
                              option === "CANCELLED" ||
                              option === "QUEUED",
                            "bg-orange-400": option === "SLEEPING"
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
