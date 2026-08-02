import type { AuthedUserResponse, UserRole } from "~/api/types";
import { hasMinRole } from "~/lib/utils";

/**
 * Hide the groups & items the user doesn't have the role for,
 * then drop the groups left without any item.
 */
export function filterGroupsByRole<
  TItem extends { minRole?: UserRole },
  TGroup extends { minRole?: UserRole; items: TItem[] }
>(groups: TGroup[], user: AuthedUserResponse | null | undefined): TGroup[] {
  if (!user) return [];

  return groups
    .filter((group) => !group.minRole || hasMinRole(user, group.minRole))
    .map((group) => ({
      ...group,
      items: group.items.filter(
        (item) => !item.minRole || hasMinRole(user, item.minRole)
      )
    }))
    .filter((group) => group.items.length > 0);
}
