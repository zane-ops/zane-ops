import * as Form from "@radix-ui/react-form";
import { useInfiniteQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { type VariantProps, cva } from "class-variance-authority";
import { Command as CommandPrimitive } from "cmdk";
import {
  CheckIcon,
  ChevronDownIcon,
  LoaderIcon,
  SearchIcon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { type DateRange } from "react-day-picker";
import { useDebounce } from "use-debounce";
import { DateRangeWithShortcuts } from "~/components/date-range-with-shortcuts";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import { Loader } from "~/components/loader";
import { Button } from "~/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator
} from "~/components/ui/command";
import { Input } from "~/components/ui/input";

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
import {
  type DeploymentLogFitlers,
  LOG_LEVELS,
  LOG_SOURCES,
  deploymentLogSearchSchema,
  deploymentQueries
} from "~/lib/queries";
import type { Writeable } from "~/lib/types";
import { cn } from "~/lib/utils";
import { isEmptyObject } from "~/utils";

export const Route = createFileRoute(
  "/_dashboard/project/$project_slug/services/docker/$service_slug/deployments/$deployment_hash/"
)({
  validateSearch: (search) => deploymentLogSearchSchema.parse(search),
  component: withAuthRedirect(DeploymentLogsDetailPage)
});

export function DeploymentLogsDetailPage(): React.JSX.Element {
  const { deployment_hash, project_slug, service_slug } = Route.useParams();
  const searchParams = Route.useSearch();
  const navigate = useNavigate();

  const [debouncedQuery] = useDebounce(searchParams.query ?? "", 300);

  const filters = {
    page: searchParams.page ?? 1,
    per_page: searchParams.per_page ?? 10,
    time_after: searchParams.time_after,
    time_before: searchParams.time_before,
    source:
      searchParams.source ?? (LOG_SOURCES as Writeable<typeof LOG_SOURCES>),
    level: searchParams.level ?? (LOG_LEVELS as Writeable<typeof LOG_LEVELS>),
    query: debouncedQuery
  } satisfies DeploymentLogFitlers;

  const logsQuery = useInfiniteQuery(
    deploymentQueries.logs({
      deployment_hash,
      project_slug,
      service_slug,
      filters
    })
  );

  if (logsQuery.isLoading) {
    return <Loader className="h-[50vh]" />;
  }

  const date: DateRange = {
    from: filters.time_after,
    to: filters.time_before
  };

  return (
    <div className="grid grid-cols-12 gap-4 mt-8">
      <div className="col-span-12 flex flex-col h-[65vh] gap-2">
        <form
          action={(formData) => {
            console.log({
              data: formData
            });
          }}
          className="rounded-t-sm w-full flex gap-2 flex-col md:flex-row flex-wrap lg:flex-nowrap"
        >
          <div className="flex items-center gap-2 order-first">
            <DateRangeWithShortcuts
              date={date}
              setDate={(newDateRange) =>
                navigate({
                  search: {
                    ...filters,
                    time_before: newDateRange?.to,
                    time_after: newDateRange?.from
                  },
                  replace: true
                })
              }
              className="min-w-[250px] w-full"
            />
          </div>

          <div className="flex w-full items-center relative flex-grow order-2">
            {logsQuery.isFetching ? (
              <LoaderIcon
                size={15}
                className="animate-spin absolute left-4 text-grey"
              />
            ) : (
              <SearchIcon size={15} className="absolute left-4 text-grey" />
            )}
            <Input
              className="px-14 w-full text-sm  bg-muted/40 dark:bg-card/30"
              placeholder="Search for log contents"
              name="query"
              defaultValue={searchParams.query}
              onKeyUp={(e) => {
                e.preventDefault();
                e.stopPropagation();
                const newQuery = e.currentTarget.value;
                if (newQuery !== (searchParams.query ?? "")) {
                  navigate({
                    search: {
                      ...filters,
                      query: e.currentTarget.value
                    },
                    replace: true
                  });
                }
              }}
            />
          </div>

          <div className="flex-shrink-0 flex items-center gap-1.5 order-1 lg:order-last">
            <SimpleMultiSelect
              value={filters.level}
              options={LOG_LEVELS as Writeable<typeof LOG_LEVELS>}
              onValueChange={(newVal) => {
                navigate({
                  search: {
                    ...filters,
                    level: newVal
                  },
                  replace: true
                });
              }}
              placeholder="log levels"
            />

            <SimpleMultiSelect
              value={filters.source}
              options={LOG_SOURCES as Writeable<typeof LOG_SOURCES>}
              onValueChange={(newVal) => {
                navigate({
                  search: {
                    ...filters,
                    source: newVal
                  },
                  replace: true
                });
              }}
              placeholder="log sources"
            />
          </div>
        </form>
        <hr className="border-border" />
        {!isEmptyObject(searchParams) && (
          <Button
            variant="outline"
            className="inline-flex w-min gap-1"
            onClick={() =>
              navigate({
                to: "./"
              })
            }
          >
            <XIcon size={15} />
            <span>Reset filters</span>
          </Button>
        )}

        <div className="rounded-md px-4 pb-2  overflow-y-auto bg-muted/25 dark:bg-card h-full w-full">
          <pre
            id="logContent"
            className="text-base whitespace-no-wrap overflow-x-scroll font-mono pt-2 relative h-full"
          >
            <div className="text-center items-center flex flex-col text-gray-500 absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
              <h3 className="text-lg font-semibold">No logs to show</h3>
              <small className="inline-block max-w-lg text-balance">
                New log entries that match your search parameters will appear
                here.
              </small>
              <button className="text-sm underline">Clear filters</button>
            </div>
          </pre>
        </div>
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
const SimpleMultiSelect = React.forwardRef<HTMLButtonElement, MultiSelectProps>(
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
    const [isPopoverOpen, setIsPopoverOpen] = React.useState(false);

    const toggleOption = (option: string) => {
      const newSelectedValues = value.includes(option)
        ? value.filter((v) => v !== option)
        : [...value, option];
      onValueChange(newSelectedValues);
    };

    const handleTogglePopover = () => {
      setIsPopoverOpen((prev) => !prev);
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
              "flex w-full p-1 pl-4 rounded-md border border-border min-h-10 h-auto items-center justify-between bg-inherit hover:bg-inherit",
              className
            )}
          >
            <div className="flex items-center justify-between w-full mx-auto">
              <div className="flex items-center">
                <span className="text-sm text-muted-foreground">
                  {placeholder}
                </span>
              </div>
              <ChevronDownIcon className="h-4 cursor-pointer text-muted-foreground mx-2" />
            </div>
          </Button>
        </PopoverTrigger>
        <PopoverContent
          className="w-[200px] p-0 border-0"
          align="end"
          sideOffset={0}
          side="bottom"
          onEscapeKeyDown={() => setIsPopoverOpen(false)}
        >
          <Command className="flex w-full flex-col rounded-md bg-popover border-border border text-popover-foreground px-2">
            <CommandPrimitive.Input
              placeholder="search"
              className="bg-inherit focus-visible:outline-none px-2 py-2"
            />
            <hr className="-mx-2 border-border" />
            <CommandPrimitive.List className="w-full overflow-y-auto overflow-x-hidden py-2">
              <CommandEmpty>No results found.</CommandEmpty>
              <CommandPrimitive.Group>
                {options.map((option) => {
                  const isSelected = value.includes(option);
                  return (
                    <CommandItem
                      key={option}
                      onSelect={() => toggleOption(option)}
                      className="cursor-pointer flex gap-1"
                    >
                      <CheckIcon
                        size={15}
                        className={cn(
                          "flex-none transition-transform duration-75",
                          isSelected ? "scale-100" : "scale-0"
                        )}
                      />
                      <div className="flex items-center justify-between w-full">
                        <span>{option}</span>
                      </div>
                    </CommandItem>
                  );
                })}
              </CommandPrimitive.Group>
            </CommandPrimitive.List>
          </Command>
        </PopoverContent>
      </Popover>
    );
  }
);
