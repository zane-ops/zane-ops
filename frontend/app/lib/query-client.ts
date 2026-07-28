import { QueryClient, keepPreviousData } from "@tanstack/react-query";
import { createDevLogger } from "~/lib/logger";
import { durationToMs } from "~/lib/utils";

const logger = createDevLogger(import.meta.url);

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
    logger.info("call makeQueryClient() from server");
    return makeQueryClient();
  }
  if (!browserQueryClient) {
    logger.info("Creating browserQueryClient", { browserQueryClient });
    browserQueryClient = makeQueryClient();
  } else {
    logger.info("Returning singleton browserQueryClient", {
      browserQueryClient
    });
  }
  return browserQueryClient;
}
