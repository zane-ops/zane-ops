import * as React from "react";
import type { SearchResource } from "~/api/types";
import { useCommandBarSearch } from "~/components/commandbar/commandbar-search";
import { useCommandBarStore } from "~/components/commandbar/commandbar-store";
import { createDevLogger } from "~/lib/logger";
import { isEditableTarget } from "~/lib/utils";

const logger = createDevLogger(import.meta.url);

/**
 * Everything the command bar tracks while it is open: what is typed, which
 * mode it puts the list in, which resource is used as the context & which item
 * is highlighted.
 *
 * The resource search lives here too because `Tab` needs to resolve the
 * highlighted item back to its resource.
 */
export function useCommandBarState() {
  const { open, setOpen, toggle } = useCommandBarStore();

  const [search, setSearch] = React.useState("");

  const [selectedResource, setSelectedResource] =
    React.useState<SearchResource | null>(null);

  /** the value of the item currently highlighted in the list */
  const [highlightedValue, setHighlightedValue] = React.useState("");

  const inputRef = React.useRef<React.ComponentRef<"input">>(null);

  const isActionMode = search.startsWith(">");

  const searchState = useCommandBarSearch({
    search,
    // Searching is pointless when the palette is closed
    // or when the list shows something else than resources
    shouldSearch: open && !isActionMode && !selectedResource
  });
  const { searchItemsByValue } = searchState;

  const clearSelectedResource = React.useCallback(() => {
    setSearch("");
    setSelectedResource(null);
  }, []);

  const handleOpenChange = React.useCallback(
    (nextOpen: boolean) => {
      logger
        .scope("useCommandBarState", "handleOpenChange")
        .info({ selectedResource, nextOpen });

      if (!nextOpen && selectedResource) return;

      if (!nextOpen) clearSelectedResource();

      setOpen(nextOpen);
    },
    [setOpen, selectedResource, clearSelectedResource]
  );

  const handleCmdInputKeyDown = React.useCallback(
    (ev: React.KeyboardEvent<HTMLDivElement>) => {
      // `Tab` selects whatever is highlighted if found
      if (ev.key === "Tab") {
        const item = searchItemsByValue.get(highlightedValue);

        logger
          .scope("useCommandBarState", "handleCmdInputKeyDown")
          .info({ highlightedValue, item, searchItemsByValue });

        ev.preventDefault();
        ev.stopPropagation();

        if (!item) return;

        setSearch("");
        setSelectedResource(item.resource);
      }
    },
    [searchItemsByValue, highlightedValue]
  );

  const handleCmdBarKeyDown = React.useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      // `escape` clears the context first, it only closes the dialog
      // once there is nothing left to clear
      logger
        .scope("useCommandBarState", "handleCmdBarKeyDown")
        .info({ selectedResource, "event.key": event.key });

      if (event.key === "Escape" && selectedResource) {
        event.preventDefault();
        event.stopPropagation();

        clearSelectedResource();
      }
    },
    [selectedResource, clearSelectedResource]
  );

  const runCmd = React.useCallback(
    (command: () => void) => {
      command();
      setOpen(false);
      clearSelectedResource();
    },
    [setOpen, clearSelectedResource]
  );

  React.useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (
        event.key.toLowerCase() !== "k" ||
        !(event.metaKey || event.ctrlKey)
      ) {
        return;
      }

      if (!open && isEditableTarget(event.target)) {
        return;
      }

      event.preventDefault();
      toggle();
      if (open) clearSelectedResource();
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, toggle, clearSelectedResource]);

  return {
    open,
    search,
    setSearch,
    isActionMode,
    selectedResource,
    highlightedValue,
    setHighlightedValue,
    inputRef,
    clearSelectedResource,
    handleOpenChange,
    handleCmdInputKeyDown,
    handleCmdBarKeyDown,
    runCmd,
    ...searchState
  };
}
