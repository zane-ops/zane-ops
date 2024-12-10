import {
  type ErrorResponse,
  isRouteErrorResponse,
  redirect
} from "react-router";
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

export function notFound(message: string = "Not Found") {
  return new Response(message, { status: 404, statusText: message });
}

export function isNotFoundError(error: unknown): error is ErrorResponse {
  return isRouteErrorResponse(error) && error.status === 404;
}
