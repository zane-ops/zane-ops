import {
  QueryClient,
  QueryClientProvider,
  keepPreviousData
} from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import * as React from "react";
import {
  Link,
  Links,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
  isRouteErrorResponse,
  useRouteError
} from "react-router";
import { Loader } from "~/components/loader";
import { Logo } from "~/components/logo";
import { TailwindIndicator } from "~/components/tailwind-indicator";
import { Button } from "~/components/ui/button";
import { Toaster } from "~/components/ui/sonner";
import type { Route } from "./+types/root";
import stylesheet from "./app.css?url";

export function links() {
  return [
    {
      rel: "icon",
      href: "/logo/ZaneOps-SYMBOL-BLACK.svg",
      media: "(prefers-color-scheme: light)"
    },
    {
      rel: "icon",
      href: "/logo/ZaneOps-SYMBOL-WHITE.svg",
      media: "(prefers-color-scheme: dark)"
    },
    { rel: "stylesheet", href: stylesheet }
  ] satisfies ReturnType<Route.LinksFunction>;
}

export function meta() {
  return [{ title: "ZaneOps" }] satisfies ReturnType<Route.MetaFunction>;
}

const ONE_HOUR = 1000 * 60 * 60;

// Create a single query client instance
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      placeholderData: keepPreviousData,
      staleTime: ONE_HOUR / 2, // Consider data stale after 30 minutes
      cacheTime: ONE_HOUR, // Keep in cache for one hour
      retry: (failureCount, error) => {
        // Only retry for network errors, not for HTTP error responses
        return (
          !(error instanceof Response && error.status >= 400 && error.status < 600) &&
          failureCount < 3
        );
      },
    },
    mutations: {
      retry: false, // Avoid retrying mutations automatically
    },
  },
});


export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <Meta />
        <Links />
        <Scripts />
      </head>
      <body>
        <QueryClientProvider client={queryClient}>
          {children}
          <Toaster />
          {!import.meta.env.PROD && (
            <>
              <ReactQueryDevtools />
              <TailwindIndicator />
            </>
          )}
        </QueryClientProvider>
        <ScrollRestoration />
      </body>
    </html>
  );
}

export default function App() {
  return <Outlet />;
}

export function HydrateFallback() {
  return <Loader />;
}

export function ErrorBoundary() {
  const error = useRouteError();
  let message = "Oops!";
  let details = "An unexpected error occurred.";
  let stack: string | undefined;

  if (isRouteErrorResponse(error)) {
    message = error.status === 404 ? "Oops!" : "Error";
    details =
      error.status === 404
        ? error.data ?? "Looks like you're lost 😛"
        : error.statusText || details;
  } else if (error instanceof Error) {
    details = error.message;
    stack = error.stack;
  }

  // Log the error to the console for server-side debugging.
  React.useEffect(() => {
    console.error("Unhandled Error:", error);
  }, [error]);

  return (
    <div className="flex flex-col gap-5 h-screen items-center justify-center px-5">
      <Logo className="md:flex" />
      <div className="flex-col flex gap-3 items-center">
        <h1 className="text-3xl font-bold">{message}</h1>
        <p className="text-lg">{details}</p>
      </div>

      {stack ? (
        <pre className="w-full p-4 overflow-x-auto rounded-md bg-red-400/20">
          <code>{stack}</code>
        </pre>
      ) : (
        <Link to="/">
          <Button>Go home</Button>
        </Link>
      )}
    </div>
  );
}
