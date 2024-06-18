export const userKeys = {
  authedUser: ["AUTHED_USER"] as const
};

export const projectKeys = {
  list: (filters: { slug?: string }) => ["PROJECT_LIST", filters] as const
};
