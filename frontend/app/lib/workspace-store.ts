import { hashKey } from "@tanstack/react-query";
import { create } from "zustand";
import type { AuthedUserResponse, WorkspaceMembership } from "~/api/types";
import { userQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";

type Workspace = NonNullable<
  Awaited<ReturnType<NonNullable<typeof userQueries.currentWorkspace.queryFn>>>
>;

type WorkspaceStore = {
  workspace: Workspace | null;
  setWorkspace: (workspace: Workspace | null) => void;
};

type WorkspaceMembershipStore = {
  membership: WorkspaceMembership | null;
  setMembership: (membership: WorkspaceMembership | null) => void;
};

export const useWorkspaceStore = create<WorkspaceStore>((set) => ({
  workspace: null,
  setWorkspace: (workspace) => set({ workspace })
}));

export const useWorkspaceMembershipStore = create<WorkspaceMembershipStore>(
  (set) => ({
    membership: null,
    setMembership: (membership) => set({ membership })
  })
);

/**
 * Only for components rendered within workspace-scoped routes
 * (workspace-layout.tsx and below), where a current workspace is guaranteed.
 */
export function useCurrentWorkspace() {
  const workspace = useWorkspaceStore((s) => s.workspace);
  if (!workspace) {
    throw new Error(
      "useCurrentWorkspace() called outside a workspace-scoped route"
    );
  }
  return workspace;
}

/**
 * Only for components rendered within workspace-scoped routes
 * (workspace-layout.tsx and below), where a current workspace is guaranteed.
 */
export function useCurrentWorkspaceMembership() {
  const membership = useWorkspaceMembershipStore((s) => s.membership);
  if (!membership) {
    throw new Error(
      "useCurrentWorkspaceMembership() called outside a membership-scoped route"
    );
  }
  return membership;
}

/**
 * Keeps the store mirroring the query cache directly,
 * so it reflects the query regardless of what triggered a change (initial
 * `ensureQueryData` in a loader, the query's own refetchInterval, or an
 * `invalidateQueries` call elsewhere e.g. after switching workspace).
 * Subscribing at module scope (rather than via a component's useEffect)
 * avoids a render/effect-ordering race: loaders already await
 * `ensureQueryData` before any component renders, so this subscription can
 * update the store in that same window, well before any component reads it.
 */
const authedUserHash = hashKey(userQueries.authedUser.queryKey);

getQueryClient()
  .getQueryCache()
  .subscribe((event) => {
    if (event.query.queryHash === authedUserHash) {
      const authedUser = event.query.state.data as
        | AuthedUserResponse
        | undefined;
      useWorkspaceMembershipStore.setState({
        membership: authedUser?.membership ?? null
      });
      useWorkspaceStore.setState({
        workspace: authedUser?.membership?.workspace ?? null
      });
    }
  });
