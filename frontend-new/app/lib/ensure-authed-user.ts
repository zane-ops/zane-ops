import { redirect } from "react-router";
import { userQueries } from "~/lib/queries";
import { queryClient } from "~/root";

export async function ensureAuthedUser() {
  const userQuery = await queryClient.ensureQueryData(userQueries.authedUser);
  const user = userQuery.data?.user;
  if (!user) {
    throw redirect("/login");
  }
  return user;
}
