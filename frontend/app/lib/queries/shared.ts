/**
 * Base query key for all resources scoped to a workspace.
 * The current workspace is server-side session state, so the react-query
 * cache must be partitioned by `workspaceId` to avoid leaking data across
 * workspaces.
 */
export const workspaceKey = (workspaceId: string) =>
  ["WORKSPACE", workspaceId] as const;
