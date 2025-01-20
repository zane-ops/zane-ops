import { type VariantProps, cva } from "class-variance-authority";
import { Command as CommandPrimitive } from "cmdk";
import { CheckIcon, ChevronDownIcon } from "lucide-react";
import * as React from "react";
import { Button } from "~/components/ui/button";
import { Command, CommandEmpty, CommandItem } from "~/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from "~/components/ui/popover";
import { cn } from "~/lib/utils";
import { capitalizeText } from "~/utils";

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
  label?: string;

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
  align?: React.ComponentProps<typeof PopoverContent>["align"];
  Icon?: React.ComponentType<React.ComponentProps<typeof ChevronDownIcon>>;
  closeOnSelect?: boolean;
  acceptArbitraryValues?: boolean;
  ref?: React.RefObject<HTMLButtonElement>;
  inputValue?: string;
  onInputValueChange?: (inputValue: string) => void;
}
export const MultiSelect = ({
  ref,
  options,
  onValueChange,
  variant,
  value: values = [],
  label = "Select options",
  animation = 0,
  maxCount = 3,
  modalPopover = false,
  asChild = false,
  className,
  align = "end",
  Icon = ChevronDownIcon,
  closeOnSelect,
  acceptArbitraryValues = false,
  inputValue: customInputValue,
  onInputValueChange,
  ...props
}: MultiSelectProps) => {
  const [isPopoverOpen, setIsPopoverOpen] = React.useState(false);

  const toggleOption = (option: string) => {
    const newSelectedValues = values.includes(option)
      ? values.filter((v) => v !== option)
      : [...values, option];

    if (closeOnSelect) {
      setIsPopoverOpen(false);
      setInputValue("");
    }
    onValueChange(newSelectedValues);
  };

  const handleTogglePopover = () => {
    setIsPopoverOpen((prev) => !prev);
  };

  const [value, setInputValue] = React.useState("");

  const inputValue = customInputValue ?? value;

  let visibleOptions = new Set(options);
  if (inputValue.trim().length > 0 && acceptArbitraryValues) {
    visibleOptions.add(inputValue.trim());
  }

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
            "flex w-full py-1 px-2 rounded-md border border-border border-dashed min-h-10 h-auto items-center justify-between bg-inherit",
            "hover:bg-accent",
            values.length === 0 && "pr-3.5",
            className
          )}
        >
          <div className="flex items-center gap-1 justify-between w-full mx-auto">
            <Icon size={15} className="cursor-pointer text-muted-foreground" />
            <div className="flex items-center gap-1">
              <span className="text-sm text-card-foreground">{label}</span>
              {values.length > 0 && (
                <>
                  <div className="h-4 bg-border w-px"></div>
                  {values.length > 2 ? (
                    <span className="text-sm rounded-md bg-grey/20 px-1 text-card-foreground">
                      {values.length} selected
                    </span>
                  ) : (
                    values.map((val) => (
                      <span
                        key={val}
                        className="text-sm rounded-md bg-grey/20 px-1 text-card-foreground"
                      >
                        {capitalizeText(val)}
                      </span>
                    ))
                  )}
                </>
              )}
            </div>
          </div>
        </Button>
      </PopoverTrigger>
      <PopoverContent
        className="w-[200px] p-0 border-0"
        align={align}
        sideOffset={0}
        side="bottom"
        onEscapeKeyDown={() => setIsPopoverOpen(false)}
      >
        <Command
          shouldFilter={!acceptArbitraryValues}
          className="flex w-full flex-col rounded-md bg-popover border-border border text-popover-foreground px-2"
        >
          <CommandPrimitive.Input
            placeholder="search"
            className="bg-inherit focus-visible:outline-hidden px-2 py-2"
            value={inputValue}
            onValueChange={(val) => {
              setInputValue(val);
              onInputValueChange?.(val);
            }}
          />
          <hr className="-mx-2 border-border" />
          <CommandPrimitive.List className="w-full overflow-y-auto overflow-x-hidden py-2">
            <CommandEmpty>No results found.</CommandEmpty>
            <CommandPrimitive.Group>
              {[...visibleOptions]
                .filter((option) => option.startsWith(inputValue))
                .map((option) => {
                  const isSelected = values.includes(option);
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
};
