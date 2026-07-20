import { type QueryClient, hashKey } from "@tanstack/react-query";
import { create } from "zustand";
import type { AuthedUserResponse, WorkspaceMembership } from "~/api/types";
import { userQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { notFound } from "~/lib/utils";

type Workspace = WorkspaceMembership["workspace"];
type User = NonNullable<AuthedUserResponse>["user"];

type UserStore = {
  user: User | null;
  setUser: (user: User | null) => void;
};

type WorkspaceStore = {
  workspace: Workspace | null;
  setWorkspace: (workspace: Workspace | null) => void;
};

type WorkspaceMembershipStore = {
  membership: WorkspaceMembership | null;
  setMembership: (membership: WorkspaceMembership | null) => void;
};

export const useUserStore = create<UserStore>((set) => ({
  user: null,
  setUser: (user) => set({ user })
}));

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
 * Only for components rendered within authenticated routes
 * (main-layout.tsx and below), where an authed user is guaranteed.
 */
export function useCurrentAuthedUser() {
  const user = useUserStore((s) => s.user);
  if (!user) {
    throw new Error(
      "useCurrentAuthedUser() called outside an authenticated route"
    );
  }
  return user;
}

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
 * Only for `clientLoader`/`clientAction` (run outside React, so the hooks
 * above can't be used there). The current workspace is embedded in
 * `authedUser.membership.workspace` (same object the `/api/workspace/`
 * endpoint used to return separately), so this fetches `authedUser` the same
 * way every other query in this codebase is fetched, and centralizes the
 * "what if there isn't one" case instead of leaving it to each call site to
 * null-check or non-null-assert.
 */
export async function getCurrentWorkspace(queryClient: QueryClient) {
  const user = await queryClient.ensureQueryData(userQueries.authedUser);
  const workspace = user?.membership?.workspace;
  if (!workspace) {
    throw notFound("[getCurrentWorkspace] Workspace not found");
  }
  return workspace;
}

/**
 * Keeps the stores mirroring the query cache directly,
 * so they reflect the query regardless of what triggered a change (initial
 * `ensureQueryData` in a loader, the query's own refetchInterval, or an
 * `invalidateQueries` call elsewhere e.g. after switching workspace).
 * Subscribing at module scope (rather than via a component's useEffect)
 * avoids a render/effect-ordering race: loaders already await
 * `ensureQueryData` before any component renders, so this subscription can
 * update the stores in that same window, well before any component reads them.
 */
const authedUserHash = hashKey(userQueries.authedUser.queryKey);

export function syncAuthStore(data: AuthedUserResponse | undefined | null) {
  console.log("[auth-store/syncAuthStore]", { data });
  useUserStore.setState({
    user: data?.user ?? null
  });
  useWorkspaceMembershipStore.setState({
    membership: data?.membership ?? null
  });
  useWorkspaceStore.setState({
    workspace: data?.membership?.workspace ?? null
  });
}

getQueryClient()
  .getQueryCache()
  .subscribe((event) => {
    // We don't subscribe to `removed` event because
    // if we query is removed, normally the page should get updated before
    // components, but while the page is loading, this component get updated and rerender all its subscribers
    if (event.type !== "removed" && event.query.queryHash === authedUserHash) {
      syncAuthStore(event.query.state.data as AuthedUserResponse | undefined);
    }
  });
