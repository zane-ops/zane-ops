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

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      placeholderData: keepPreviousData,
      retry: 3
    }
  }
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
  let message = "Oops!";
  let details = "An unexpected error occurred.";
  let stack: string | undefined;
  const error = useRouteError();

  if (isRouteErrorResponse(error)) {
    message = error.status === 404 ? "Oops!" : "Error";
    details =
      error.status === 404
        ? "Looks like you're lost 😛"
        : error.statusText || details;
  } else if (error && error instanceof Error) {
    details = error.message;
    stack = error.stack;
  }

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
