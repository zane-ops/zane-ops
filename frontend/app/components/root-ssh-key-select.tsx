import { Command as CommandPrimitive } from "cmdk";
import {
  CheckIcon,
  ChevronDownIcon,
  KeyRoundIcon,
  SearchIcon
} from "lucide-react";
import * as React from "react";
import type { SSHKey } from "~/api/types";
import { Button } from "~/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandItem,
  CommandList
} from "~/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from "~/components/ui/popover";
import { cn } from "~/lib/utils";

export type RootSSHKeySelectProps = {
  name: string;
  label: string;
  keys: SSHKey[];
  errors?: string[];
};

export function RootSSHKeySelect({
  name,
  label,
  keys,
  errors
}: RootSSHKeySelectProps) {
  const [isPopoverOpen, setPopoverOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [selectedKeyId, setSelectedKeyId] = React.useState<number | null>(null);

  const selectedKey =
    keys.find((key) => key.id === selectedKeyId) ?? keys[0] ?? null;

  const filteredKeys = keys.filter((key) =>
    `${key.name} ${key.fingerprint ?? ""}`
      .toLowerCase()
      .includes(query.trim().toLowerCase())
  );

  const errorId = `${name}-error`;

  return (
    <fieldset className="flex flex-col gap-1.5 flex-1">
      <label htmlFor={name}>{label}</label>

      {selectedKey && (
        <input type="hidden" name={name} value={selectedKey.id} />
      )}

      <Popover open={isPopoverOpen} onOpenChange={setPopoverOpen}>
        <PopoverTrigger asChild>
          <Button
            id={name}
            variant="outline"
            type="button"
            className="justify-between"
            aria-describedby={errorId}
            aria-invalid={!!errors}
          >
            {selectedKey ? (
              <span className="inline-flex items-center gap-2 min-w-0">
                <KeyRoundIcon className="size-4 flex-none text-grey" />
                <span>{selectedKey.name}</span>
                <span className="text-grey text-xs font-mono truncate">
                  {selectedKey.fingerprint?.toLowerCase()}
                </span>
              </span>
            ) : (
              <span className="text-sm">Select a SSH key</span>
            )}
            <ChevronDownIcon className="size-4 flex-none" />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          className={cn(
            "!w-(--radix-popover-trigger-width) p-0 z-999 shadow-md rounded-lg",
            "[&_[data-slot='command-list-wrapper']_*]:static",
            "[&_[data-slot='command-input-wrapper']]:px-2"
          )}
          align="center"
        >
          <Command shouldFilter={false} className="w-full">
            <div className="flex px-3 py-3.5 items-center gap-1">
              <SearchIcon className="size-4 flex-none text-grey" />
              <CommandPrimitive.Input
                placeholder="Search SSH keys"
                className="text-sm bg-inherit focus-visible:outline-hidden px-2 w-full"
                onValueChange={setQuery}
                value={query}
              />
            </div>
            <hr className="w-full border-border" />
            <CommandList className="flex flex-col gap-2 min-w-32 md:min-w-42 w-full bg-transparent border-none">
              <CommandEmpty>No root SSH keys found.</CommandEmpty>

              {filteredKeys.map((key) => {
                const isSelected = key.id === selectedKey?.id;

                return (
                  <CommandItem
                    key={key.id}
                    value={key.id.toString()}
                    onSelect={() => {
                      setSelectedKeyId(key.id);
                      setQuery("");
                      setPopoverOpen(false);
                    }}
                    className="cursor-pointer flex gap-1.5"
                  >
                    <div className="flex items-center justify-between w-full gap-4 min-w-0">
                      <span className="inline-flex items-start gap-2 min-w-0">
                        <KeyRoundIcon className="size-4 flex-none text-grey !relative top-0.5" />
                        <span className="inline-flex flex-col items-start">
                          <span>{key.name}</span>
                          <span className="text-grey text-xs font-mono truncate">
                            {key.fingerprint?.toLowerCase()}
                          </span>
                        </span>
                      </span>

                      <span className="flex size-4 items-center justify-center flex-none py-2.5">
                        {isSelected && (
                          <CheckIcon className="size-4 text-grey" />
                        )}
                      </span>
                    </div>
                  </CommandItem>
                );
              })}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>

      {errors && (
        <span id={errorId} className="text-red-500 text-sm">
          {errors}
        </span>
      )}
    </fieldset>
  );
}
