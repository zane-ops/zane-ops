import { QueryClient, keepPreviousData } from "@tanstack/react-query";
import { durationToMs } from "~/utils";

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        refetchOnWindowFocus: false,
        placeholderData: keepPreviousData,
        gcTime: durationToMs(3, "days"),
        retry(failureCount, error) {
          // error responses are valid responses that react router can handle, so we don't want to retry them
          return !(error instanceof Response) && failureCount < 3;
        }
      }
    }
  });
}

let browserQueryClient: QueryClient | undefined;

export function getQueryClient() {
  if (typeof window === "undefined") {
    console.log("[getQueryClient] call makeQueryClient() from server");
    return makeQueryClient();
  }
  if (!browserQueryClient) {
    console.log("[getQueryClient] Creating browserQueryClient", {
      browserQueryClient
    });
    browserQueryClient = makeQueryClient();
  } else {
    console.log("[getQueryClient] Returning singleton browserQueryClient", {
      browserQueryClient
    });
  }
  return browserQueryClient;
}
