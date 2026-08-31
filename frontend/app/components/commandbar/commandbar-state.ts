import * as React from "react";
import type { SearchResource } from "~/api/types";
import { useCurrentSelectedResourceInRouteContext } from "~/components/commandbar/commandbar-resource-actions";
import { useCommandBarSearch } from "~/components/commandbar/commandbar-search";
import { useCommandBarStore } from "~/components/commandbar/commandbar-store";
import type { CommandBarView } from "~/components/commandbar/commandbar-types";
import { createDevLogger } from "~/lib/logger";
import { isEditableTarget } from "~/lib/utils";

const logger = createDevLogger(import.meta.url);

/** the views `escape` steps out of, instead of closing the dialog */
function canExitView(view: CommandBarView) {
  return view.type === "resource" || view.type === "workspace";
}

/**
 * Everything the command bar tracks while it is open: what is typed, which
 * view it puts the list in & which item is highlighted.
 *
 * The resource search lives here too because `Tab` needs to resolve the
 * highlighted item back to its resource.
 */
export function useCommandBarState() {
  const {
    open,
    setOpen,
    toggle,
    view: storedView,
    setView
  } = useCommandBarStore();

  const [search, setSearch] = React.useState("");

  const selectedResourceInContext = useCurrentSelectedResourceInRouteContext();

  const [selectedResource, setSelectedResource] =
    React.useState<SearchResource | null>(null);

  /** the value of the item currently highlighted in the list */
  const [highlightedValue, setHighlightedValue] = React.useState("");

  const inputRef = React.useRef<React.ComponentRef<"input">>(null);

  // only `home` & `workspace` are stored, the other two are implied by the
  // state that puts the bar in them
  const view: CommandBarView = React.useMemo(() => {
    if (selectedResource) {
      return { type: "resource", resource: selectedResource };
    }
    if (storedView !== "home") {
      return { type: storedView };
    }
    if (search.startsWith(">")) {
      return { type: "action" };
    }
    return { type: "home" };
  }, [selectedResource, storedView, search]);

  const searchState = useCommandBarSearch({
    search,
    // Searching is pointless when the palette is closed
    // or when the list shows something else than resources
    shouldSearch: open && view.type === "home"
  });
  const { searchItemsById } = searchState;

  /**
   * Back to a blank `home` view: the search holds the `action` view &
   * the selected resource the `resource` one, so both have to go.
   */
  const exitView = React.useCallback(() => {
    setSearch("");
    setSelectedResource(null);
    setView("home");
  }, [setView]);

  // `view` is a new object on every render, the callbacks below depend on
  // this boolean instead so they keep a stable identity
  const canExit = canExitView(view);

  const handleOpenChange = React.useCallback(
    (nextOpen: boolean) => {
      logger
        .scope("useCommandBarState", "handleOpenChange")
        .info({ canExit, nextOpen });

      // `escape` is handled by `handleCmdBarKeyDown`, it steps out of the
      // current view before the dialog is allowed to close
      if (!nextOpen && canExit) return;

      if (!nextOpen) exitView();

      setOpen(nextOpen);
    },
    [setOpen, canExit, exitView]
  );

  const handleCmdInputKeyDown = React.useCallback(
    (ev: React.KeyboardEvent<HTMLDivElement>) => {
      // `Tab` selects whatever is highlighted if found. `highlightedValue`
      // is the item's `id`, set as its `value` in the list
      if (ev.key === "Tab") {
        const item = searchItemsById.get(highlightedValue);

        logger
          .scope("useCommandBarState", "handleCmdInputKeyDown")
          .info({ highlightedValue, item, searchItemsById });

        ev.preventDefault();
        ev.stopPropagation();

        if (!item) return;

        setSearch("");
        setSelectedResource(item.resource);
      }
    },
    [searchItemsById, highlightedValue]
  );

  const handleCmdBarKeyDown = React.useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      // `escape` clears the context first, it only closes the dialog
      // once there is nothing left to clear
      logger
        .scope("useCommandBarState", "handleCmdBarKeyDown")
        .info({ canExit, "event.key": event.key });

      if (event.key !== "Escape" || !canExit) return;

      event.preventDefault();
      event.stopPropagation();

      exitView();
    },
    [canExit, exitView]
  );

  /**
   * `keepOpen` is for the commands that only switch the bar to another view,
   * closing it would defeat their purpose.
   */
  const runCmd = React.useCallback(
    (
      command: () => void,
      { keepOpen = false }: { keepOpen?: boolean } = {}
    ) => {
      command();

      if (keepOpen) {
        // the query that got us here means nothing to the view we land in
        setSearch("");
        inputRef.current?.focus();
        return;
      }

      setOpen(false);
      exitView();
    },
    [setOpen, exitView]
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
      if (open) exitView();
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, toggle, exitView]);

  /**
   * The selected in context should only run when the `open` state change
   */
  const wasOpen = React.useRef(open);
  React.useEffect(() => {
    const justOpened = open && !wasOpen.current;
    wasOpen.current = open;

    if (justOpened && storedView === "home" && selectedResourceInContext) {
      setSelectedResource(selectedResourceInContext);
    }
    setSelectedResource(selectedResourceInContext);
  }, [open, storedView, selectedResourceInContext]);

  return {
    open,
    search,
    setSearch,
    view,
    setView,
    exitView,
    highlightedValue,
    setHighlightedValue,
    inputRef,
    handleOpenChange,
    handleCmdInputKeyDown,
    handleCmdBarKeyDown,
    runCmd,
    ...searchState
  };
}
