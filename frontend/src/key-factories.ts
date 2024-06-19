export const userKeys = {
  authedUser: ["AUTHED_USER"] as const
};

export const projectKeys = {
  list: (filters: {
    slug?: string;
    page?: number;
    per_page?: number;
    sort_by?: ("slug" | "-slug" | "updated_at" | "-updated_at")[];
  }) => ["PROJECT_LIST", filters] as const
};
