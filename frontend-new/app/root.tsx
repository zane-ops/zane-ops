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
  ScrollRestoration
} from "react-router";
import { TailwindIndicator } from "~/components/tailwind-indicator";
import type { Route } from "./+types/root";
import stylesheet from "./app.css?url";

export const links: Route.LinksFunction = () => [
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
];

export const meta: Route.MetaFunction = () => [{ title: "ZaneOps" }];

export function Layout({ children }: { children: React.ReactNode }) {
  const [queryClient] = React.useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            refetchOnWindowFocus: false,
            placeholderData: keepPreviousData,
            retry: 3
          }
        }
      })
  );
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <Meta />
        <Links />
      </head>
      <body>
        <QueryClientProvider client={queryClient}>
          <div className="flex items-center gap-2 ">
            <Link prefetch="intent" className="text-link underline" to="/login">
              Login
            </Link>
            <Link prefetch="intent" className="text-link underline" to="/">
              Home
            </Link>
          </div>
          {children}
          {!import.meta.env.PROD && (
            <>
              <ReactQueryDevtools />
              <TailwindIndicator />
            </>
          )}
        </QueryClientProvider>
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

export default function App() {
  return <Outlet />;
}

export function HydrateFallback() {
  return <p>Loading Game...</p>;
}
