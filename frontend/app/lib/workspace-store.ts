import { hashKey } from "@tanstack/react-query";
import { create } from "zustand";
import { userQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";

type Workspace = NonNullable<
  Awaited<ReturnType<NonNullable<typeof userQueries.currentWorkspace.queryFn>>>
>;

type WorkspaceStore = {
  workspace: Workspace | null;
  setWorkspace: (workspace: Workspace | null) => void;
};

export const useWorkspaceStore = create<WorkspaceStore>((set) => ({
  workspace: null,
  setWorkspace: (workspace) => set({ workspace })
}));

/**
 * Only for components rendered within workspace-scoped routes
 * (workspace-layout.tsx and below), where a current workspace is guaranteed.
 */
export function useCurrentWorkspaceId() {
  const id = useWorkspaceStore((s) => s.workspace?.id);
  if (!id) {
    throw new Error(
      "useCurrentWorkspaceId() called outside a workspace-scoped route"
    );
  }
  return id;
}

/**
 * Keeps the store mirroring `userQueries.currentWorkspace`'s cache directly,
 * so it reflects the query regardless of what triggered a change (initial
 * `ensureQueryData` in a loader, the query's own refetchInterval, or an
 * `invalidateQueries` call elsewhere e.g. after switching workspace).
 * Subscribing at module scope (rather than via a component's useEffect)
 * avoids a render/effect-ordering race: loaders already await
 * `ensureQueryData` before any component renders, so this subscription can
 * update the store in that same window, well before any component reads it.
 */
const currentWorkspaceHash = hashKey(userQueries.currentWorkspace.queryKey);

getQueryClient()
  .getQueryCache()
  .subscribe((event) => {
    if (event.query.queryHash === currentWorkspaceHash) {
      useWorkspaceStore.setState({
        workspace: (event.query.state.data as Workspace | undefined) ?? null
      });
    }
  });
