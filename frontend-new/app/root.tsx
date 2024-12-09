import {
  QueryClient,
  QueryClientProvider,
  keepPreviousData
} from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import * as React from "react";
import { Links, Meta, Outlet, Scripts, ScrollRestoration } from "react-router";
import { Loader } from "~/components/loader";
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
