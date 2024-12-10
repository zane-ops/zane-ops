import { type ErrorResponse, isRouteErrorResponse } from "react-router";

export function notFound(message: string = "Not Found") {
  return new Response(message, { status: 404, statusText: message });
}

export function isNotFoundError(error: unknown): error is ErrorResponse {
  return isRouteErrorResponse(error) && error.status === 404;
}
