import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { format } from "date-fns";
import {
  Ban,
  CalendarIcon,
  CheckIcon,
  ChevronDown,
  Container,
  EllipsisVertical,
  Eye,
  Hash,
  LoaderIcon,
  Redo2,
  ScrollText,
  Timer
} from "lucide-react";
import * as React from "react";
import type { DateRange } from "react-day-picker";
import { withAuthRedirect } from "~/components/helper/auth-redirect";

import { Button, SubmitButton } from "~/components/ui/button";
import { Calendar } from "~/components/ui/calendar";

import { type VariantProps, cva } from "class-variance-authority";

import { Loader } from "~/components/loader";
import { Pagination } from "~/components/pagination";
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
import { serviceDeploymentListFilters } from "~/key-factories";
import { DEPLOYMENT_STATUSES } from "~/lib/constants";
import { useDeployDockerServiceMutation } from "~/lib/hooks/use-deploy-service-mutation";
import { useDockerServiceDeploymentListQuery } from "~/lib/hooks/use-docker-service-deployment-list-query";
import type { Writeable } from "~/lib/types";
import { cn } from "~/lib/utils";
import {
  capitalizeText,
  formatElapsedTime,
  mergeTimeAgoFormatterAndFormattedDate
} from "~/utils";

export const Route = createFileRoute(
  "/_dashboard/project/$project_slug/services/docker/$service_slug/"
)({
  validateSearch: (search) => serviceDeploymentListFilters.parse(search),
  component: withAuthRedirect(ServiceDetails)
});

function ServiceDetails() {
  const { project_slug, service_slug } = Route.useParams();
  const searchParams = Route.useSearch();
  const navigate = useNavigate();

  const filters = {
    page: searchParams.page ?? 1,
    per_page: searchParams.per_page ?? 10,
    status:
      searchParams.status ??
      (DEPLOYMENT_STATUSES as Writeable<typeof DEPLOYMENT_STATUSES>),
    queued_at_after: searchParams.queued_at_after,
    queued_at_before: searchParams.queued_at_before
  };

  const deploymentListQuery = useDockerServiceDeploymentListQuery(
    project_slug,
    service_slug,
    filters
  );
  const { isPending: isDeploying, mutate: deploy } =
    useDeployDockerServiceMutation(project_slug, service_slug);

  if (deploymentListQuery.isLoading) {
    return <Loader className="h-[50vh]" />;
  }

  const date: DateRange = {
    from: filters.queued_at_after,
    to: filters.queued_at_before
  };
  // I wanted to make a function called `isObjectEmpty` to check that no search params have been done,
  // But TS keeps giving me stupid errors and I don't want to deal with it
  const noFilters =
    !searchParams.page &&
    !searchParams.per_page &&
    !searchParams.status &&
    !searchParams.queued_at_after &&
    !searchParams.queued_at_before;

  const deploymentList = deploymentListQuery.data?.data?.results ?? [];
  const currentProductionDeployment = deploymentList.find(
    (dpl) => dpl.is_current_production
  );

  const newDeployments = deploymentList.filter((dpl) => !dpl.finished_at);

  const previousDeployments = deploymentList.filter(
    (dpl) => dpl.finished_at && dpl.hash !== currentProductionDeployment?.hash
  );

  const noDeploymentsYet = deploymentList.length === 0 && noFilters;
  const noResultsFound: boolean = !noFilters && deploymentList.length === 0;

  const totalDeployments = deploymentListQuery.data?.data?.count ?? 0;
  const totalPages = Math.ceil(totalDeployments / filters.per_page);

  return (
    <>
      {noDeploymentsYet ? (
        <div className="flex justify-center items-center">
          <div className=" flex gap-1 flex-col items-center mt-40">
            <h1 className="text-2xl font-bold">No Deployments made yet</h1>
            <h2 className="text-lg">Your service is offline</h2>
            <form action={() => deploy({})}>
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
            </form>
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
                  onSelect={(range) =>
                    navigate({
                      search: {
                        ...filters,
                        queued_at_before: range?.to,
                        queued_at_after: range?.from
                      },
                      replace: true
                    })
                  }
                  numberOfMonths={2}
                />
              </PopoverContent>
            </Popover>
            <div className="w-fit">
              <DeploymentStatusesMultiSelect
                options={DEPLOYMENT_STATUSES as unknown as string[]}
                onValueChange={(values) =>
                  navigate({
                    search: {
                      ...filters,
                      status: values
                    },
                    replace: true
                  })
                }
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
                  <Link href=".">Clear filters</Link>
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
                          <DeploymentCard
                            commit_message={deployment.commit_message}
                            hash={deployment.hash}
                            status={deployment.status}
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
                          />
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
                {currentProductionDeployment && (
                  <section className="flex flex-col gap-2">
                    <h2 className="text-gray-400 text-sm">Current</h2>
                    <DeploymentCard
                      commit_message={
                        currentProductionDeployment.commit_message
                      }
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
                    />
                  </section>
                )}
                {previousDeployments.length > 0 && (
                  <section className="flex flex-col gap-2">
                    <h2 className="text-gray-400 text-sm">Previous</h2>
                    <ul className="flex flex-col gap-4">
                      {previousDeployments.map((deployment) => (
                        <li key={deployment.hash}>
                          <DeploymentCard
                            commit_message={deployment.commit_message}
                            hash={deployment.hash}
                            status={deployment.status}
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
                          />
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
              </>
            )}
          </div>
          {!noDeploymentsYet && !noResultsFound && (
            <div className="my-4 block">
              <Pagination
                totalPages={totalPages}
                currentPage={filters.page}
                perPage={filters.per_page}
                onChangePage={(newPage) => {
                  navigate({
                    search: { ...filters, page: newPage },
                    replace: true
                  });
                }}
                onChangePerPage={(newPerPage) => {
                  navigate({
                    search: {
                      ...filters,
                      page: 1,
                      per_page: newPerPage
                    },
                    replace: true
                  });
                }}
              />
            </div>
          )}
        </>
      )}
    </>
  );
}

type DeploymentCardProps = {
  status:
    | "QUEUED"
    | "PREPARING"
    | "STARTING"
    | "RESTARTING"
    | "HEALTHY"
    | "UNHEALTHY"
    | "SLEEPING"
    | "FAILED"
    | "REMOVED"
    | "CANCELLED";
  started_at?: Date;
  finished_at?: Date;
  queued_at: Date;
  commit_message: string;
  image: string;
  hash: string;
  is_current_production?: boolean;
};

function DeploymentCard({
  status,
  started_at,
  finished_at,
  queued_at,
  commit_message,
  image,
  hash,
  is_current_production = false
}: DeploymentCardProps) {
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

  if (!image.includes(":")) {
    image += ":latest";
  }

  return (
    <div
      className={cn(
        "flex border group  px-3 py-4 rounded-md  bg-opacity-10 justify-between items-center relative",
        {
          "border-blue-600 bg-blue-600":
            status === "STARTING" ||
            status === "RESTARTING" ||
            status === "PREPARING",
          "border-green-600 bg-green-600": status === "HEALTHY",
          "border-red-600 bg-red-600":
            status === "UNHEALTHY" || status === "FAILED",
          "border-gray-600 bg-gray-600":
            status === "REMOVED" ||
            status === "CANCELLED" ||
            status === "QUEUED",
          "border-yellow-600 bg-yellow-600": status === "SLEEPING"
        }
      )}
    >
      <div className="flex ">
        {/* Status name */}
        <div className="w-[160px]">
          <h3 className="flex items-center gap-1 capitalize">
            <span
              className={cn("text-lg", {
                "text-blue-500":
                  status === "STARTING" ||
                  status === "RESTARTING" ||
                  status === "PREPARING",
                "text-green-500": status === "HEALTHY",
                "text-red-500": status === "UNHEALTHY" || status === "FAILED",
                "text-gray-500 dark:text-gray-400":
                  status === "REMOVED" ||
                  status === "CANCELLED" ||
                  status === "QUEUED",
                "text-yellow-500": status === "SLEEPING"
              })}
            >
              {capitalizeText(status)}
            </span>
            {Boolean(started_at && !finished_at) && (
              <LoaderIcon className="animate-spin" size={15} />
            )}
          </h3>
          <p className="text-sm text-gray-400 text-nowrap">
            {mergeTimeAgoFormatterAndFormattedDate(queued_at)}
          </p>
        </div>

        {/* Commit message & timer */}
        <div className="flex flex-col items-start gap-1">
          <h3>
            <Link
              className="after:absolute after:inset-0"
              to={`./deployments/${hash}`}
            >
              {capitalizeText(commit_message)}
            </Link>
          </h3>
          <div className="flex text-gray-400 gap-2.5 text-sm w-full items-center">
            <div className="gap-0.5 inline-flex items-center">
              <Timer size={15} />
              {started_at && !finished_at ? (
                <span>{formatElapsedTime(timeElapsed)}</span>
              ) : started_at && finished_at ? (
                <span>
                  {formatElapsedTime(
                    Math.round(
                      (finished_at.getTime() - started_at.getTime()) / 1000
                    )
                  )}
                </span>
              ) : (
                !started_at && !finished_at && <span>-</span>
              )}
            </div>
            <div className="gap-1 inline-flex items-center">
              <Container size={15} />
              <span>{image}</span>
            </div>
            <div className="inline-flex items-center gap-0.5 right-1">
              <Hash size={15} />
              <span>{hash}</span>
            </div>
          </div>
        </div>
      </div>

      {/* View logs button & triple dot */}
      <div className="flex items-center gap-2 relative z-10">
        <Button
          asChild
          variant="ghost"
          className={cn("border hover:bg-inherit focus:opacity-100", {
            "border-blue-600":
              status === "STARTING" ||
              status === "RESTARTING" ||
              status === "PREPARING",
            "border-green-600": status === "HEALTHY",
            "border-red-600": status === "UNHEALTHY" || status === "FAILED",
            "border-gray-600 opacity-0 group-hover:opacity-100 transition-opacity ease-in duration-150":
              status === "REMOVED" ||
              status === "CANCELLED" ||
              status === "QUEUED",
            "border-yellow-600": status === "SLEEPING"
          })}
        >
          <Link to={`deployments/${hash}`}>View logs</Link>
        </Button>

        <Menubar className="border-none h-auto md:block hidden w-fit">
          <MenubarMenu>
            <MenubarTrigger
              className="flex justify-center items-center gap-2"
              asChild
            >
              <Button variant="ghost" className="px-1.5 py-1 hover:bg-inherit">
                <EllipsisVertical />
              </Button>
            </MenubarTrigger>
            <MenubarContent
              side="bottom"
              align="start"
              className="border min-w-0 mx-9 border-border"
            >
              <MenubarContentItem
                icon={Eye}
                text="Details"
                onClick={() => {
                  navigate({
                    to: `deployments/${hash}/details`
                  });
                }}
              />
              <MenubarContentItem
                icon={ScrollText}
                text="View logs"
                onClick={() => {
                  navigate({
                    to: `deployments/${hash}`
                  });
                }}
              />
              {!is_current_production && finished_at && (
                <MenubarContentItem icon={Redo2} text="Redeploy" />
              )}
              {!finished_at && (
                <MenubarContentItem
                  className="text-red-500"
                  icon={Ban}
                  text="Cancel"
                />
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
const DeploymentStatusesMultiSelect = React.forwardRef<
  HTMLButtonElement,
  MultiSelectProps
>(
  (
    {
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
    },
    ref
  ) => {
    // const [selectedValues, setSelectedValues] =
    //   React.useState<string[]>(defaultValue);
    const [isPopoverOpen, setIsPopoverOpen] = React.useState(false);

    // React.useEffect(() => {
    //   if (JSON.stringify(selectedValues) !== JSON.stringify(defaultValue)) {
    //     setSelectedValues(selectedValues);
    //   }
    // }, [defaultValue, selectedValues]);

    const handleInputKeyDown = (
      event: React.KeyboardEvent<HTMLInputElement>
    ) => {
      if (event.key === "Enter") {
        setIsPopoverOpen(true);
      } else if (event.key === "Backspace" && !event.currentTarget.value) {
        // const newSelectedValues = [...selectedValues];
        // newSelectedValues.pop();
        // setSelectedValues(newSelectedValues);
        // onValueChange(newSelectedValues);
      }
    };

    const toggleOption = (option: string) => {
      const newSelectedValues = value.includes(option)
        ? value.filter((v) => v !== option)
        : [...value, option];
      // onValueChange(newSelectedValues);
      onValueChange(newSelectedValues);
    };

    const handleClear = () => {
      // setSelectedValues([]);
      onValueChange([]);
    };

    const handleTogglePopover = () => {
      setIsPopoverOpen((prev) => !prev);
    };

    const toggleAll = () => {
      if (value.length === options.length) {
        handleClear();
      } else {
        // setSelectedValues(options);
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
                <div className="mx-2 flex items-center w-20 overflow-visible">
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
  }
);
