import { type VariantProps, cva } from "class-variance-authority";
import {
  CheckIcon,
  ChevronDown,
  WandSparkles,
  XCircle,
  XIcon
} from "lucide-react";
import * as React from "react";

import { cn } from "../../lib/utils";
import { Badge } from "./badge";
import { Button } from "./button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator
} from "./command";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";
import { Separator } from "./separator";

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

/**
 * Props for MultiSelect component
 */
interface MultiSelectProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof multiSelectVariants> {
  /**
   * An array of option objects to be displayed in the multi-select component.
   * Each option object has a label, value, and an optional icon.
   */
  options: {
    /** The text to display for the option. */
    label: string;
    /** The unique value associated with the option. */
    value: string;
    /** Optional icon component to display alongside the option. */
    icon?: React.ComponentType<{ className?: string }>;
    color: string;
  }[];

  /**
   * Callback function triggered when the selected values change.
   * Receives an array of the new selected values.
   */
  onValueChange: (value: string[]) => void;

  /** The default selected values when the component mounts. */
  defaultValue: string[];

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
}

export const MultiSelect = React.forwardRef<
  HTMLButtonElement,
  MultiSelectProps
>(
  (
    {
      options,
      onValueChange,
      variant,
      defaultValue = [],
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
    const [selectedValues, setSelectedValues] =
      React.useState<string[]>(defaultValue);
    const [isPopoverOpen, setIsPopoverOpen] = React.useState(false);

    React.useEffect(() => {
      if (JSON.stringify(selectedValues) !== JSON.stringify(defaultValue)) {
        setSelectedValues(selectedValues);
      }
    }, [defaultValue, selectedValues]);

    const handleInputKeyDown = (
      event: React.KeyboardEvent<HTMLInputElement>
    ) => {
      if (event.key === "Enter") {
        setIsPopoverOpen(true);
      } else if (event.key === "Backspace" && !event.currentTarget.value) {
        const newSelectedValues = [...selectedValues];
        newSelectedValues.pop();
        setSelectedValues(newSelectedValues);
        onValueChange(newSelectedValues);
      }
    };

    const toggleOption = (value: string) => {
      const newSelectedValues = selectedValues.includes(value)
        ? selectedValues.filter((v) => v !== value)
        : [...selectedValues, value];
      setSelectedValues(newSelectedValues);
      onValueChange(newSelectedValues);
    };

    const handleClear = () => {
      setSelectedValues([]);
      onValueChange([]);
    };

    const handleTogglePopover = () => {
      setIsPopoverOpen((prev) => !prev);
    };

    const clearExtraOptions = () => {
      const newSelectedValues = selectedValues.slice(0, maxCount);
      setSelectedValues(newSelectedValues);
      onValueChange(newSelectedValues);
    };

    const toggleAll = () => {
      if (selectedValues.length === options.length) {
        handleClear();
      } else {
        const allValues = options.map((option) => option.value);
        setSelectedValues(allValues);
        onValueChange(allValues);
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
                        "bg-gray-400": selectedValues.includes("QUEUED"),
                        "bg-none": !selectedValues.includes("QUEUED")
                      }
                    )}
                  />

                  <div
                    className={cn(
                      "w-3 flex-none h-3 border relative -left-1 border-border rounded-full",
                      {
                        "bg-gray-400": selectedValues.includes("CANCELLED"),
                        "bg-none": !selectedValues.includes("CANCELLED")
                      }
                    )}
                  />

                  <div
                    className={cn(
                      "w-3 flex-none relative -left-2 h-3 border border-border rounded-full",
                      {
                        "bg-red-400": selectedValues.includes("FAILED"),
                        "bg-none": !selectedValues.includes("FAILED")
                      }
                    )}
                  />

                  <div
                    className={cn(
                      "w-3 flex-none h-3 relative -left-3 border border-border rounded-full",
                      {
                        "bg-blue-400": selectedValues.includes("PREPARING"),
                        "bg-none": !selectedValues.includes("PREPARING")
                      }
                    )}
                  />

                  <div
                    className={cn(
                      "w-3 flex-none h-3 relative -left-4 border border-border rounded-full",
                      {
                        "bg-green-400": selectedValues.includes("HEALTHY"),
                        "bg-none": !selectedValues.includes("HEALTHY")
                      }
                    )}
                  />

                  <div
                    className={cn(
                      "w-3 flex-none h-3 border relative -left-5 border-border rounded-full",
                      {
                        "bg-red-400": selectedValues.includes("UNHEALTHY"),
                        "bg-none": !selectedValues.includes("UNHEALTHY")
                      }
                    )}
                  />

                  <div
                    className={cn(
                      "w-3 flex-none h-3 border relative -left-6 border-border rounded-full",
                      {
                        "bg-blue-400": selectedValues.includes("STARTING"),
                        "bg-none": !selectedValues.includes("STARTING")
                      }
                    )}
                  />

                  <div
                    className={cn(
                      "w-3 flex-none h-3 border relative -left-7 border-border rounded-full",
                      {
                        "bg-blue-400": selectedValues.includes("RESTARTING"),
                        "bg-none": !selectedValues.includes("RESTARTING")
                      }
                    )}
                  />

                  <div
                    className={cn(
                      "w-3 flex-none h-3 border relative -left-8 border-border rounded-full",
                      {
                        "bg-gray-400": selectedValues.includes("REMOVED"),
                        "bg-none": !selectedValues.includes("REMOVED")
                      }
                    )}
                  />

                  <div
                    className={cn(
                      "w-3 flex-none h-3 border relative -left-9 border-border rounded-full",
                      {
                        "bg-orange-400": selectedValues.includes("SLEEPING"),
                        "bg-none": !selectedValues.includes("SLEEPING")
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
              placeholder="Search..."
              onKeyDown={handleInputKeyDown}
            />
            <CommandList>
              <CommandEmpty>No results found.</CommandEmpty>
              <CommandGroup>
                {options.map((option) => {
                  const isSelected = selectedValues.includes(option.value);
                  return (
                    <CommandItem
                      key={option.value}
                      onSelect={() => toggleOption(option.value)}
                      className="cursor-pointer"
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
                      {option.icon && (
                        <option.icon className="mr-2 h-4 w-4 text-muted-foreground" />
                      )}
                      <div className="flex items-center justify-between w-full">
                        <span>{option.label}</span>

                        <div
                          className={cn(
                            "relative rounded-full bg-green-400 w-2.5 h-2.5",
                            {
                              "bg-green-600 ": option.color === "green",
                              "bg-red-400": option.color === "red",
                              "bg-orange-400": option.color === "orange",
                              "bg-gray-400": option.color === "gray",
                              "bg-blue-400": option.color === "blue"
                            },
                            className
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

MultiSelect.displayName = "MultiSelect";
