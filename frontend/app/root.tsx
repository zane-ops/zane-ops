import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";
import {
  QueryClient,
  QueryClientProvider,
  keepPreviousData
} from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import {
  PersistQueryClientProvider,
  removeOldestQuery
} from "@tanstack/react-query-persist-client";
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
import { ThemeProvider } from "~/components/theme-provider";
import { Button } from "~/components/ui/button";
import { Toaster } from "~/components/ui/sonner";
import { THEME_COOKIE_KEY } from "~/lib/constants";
import { durationToMs } from "~/utils";
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
      gcTime: durationToMs(3, "days"),
      retry(failureCount, error) {
        // error responses are valid responses that react router can handle, so we don't want to retry them
        return !(error instanceof Response) && failureCount < 3;
      }
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
      </head>
      <body className="overflow-x-clip">
        {children}

        <ScrollRestoration />
        <Scripts />

        <script
          dangerouslySetInnerHTML={{
            __html: `
                (function () {
                  function getCookieValue(cookieName) {
                    // Split all cookies into an array
                    var cookies = document.cookie.split(';');
                  
                    // Loop through the cookies
                    for (var i = 0; i < cookies.length; i++) {
                      var cookie = cookies[i].trim();
                  
                      // Check if the cookie starts with the given name
                      if (cookie.indexOf(cookieName + '=') === 0) {
                        // Extract and return the cookie value
                        return cookie.substring(cookieName.length + 1);
                      }
                    }
                  
                    // Return null if the cookie is not found
                    return null;
                  }

                  function setTheme(newTheme) {
                    if (newTheme === 'DARK') {
                      document.documentElement.dataset.theme = 'dark';
                    } else if (newTheme === 'LIGHT') {
                      document.documentElement.dataset.theme = 'light';
                    }
                  }

                  var initialTheme = getCookieValue('${THEME_COOKIE_KEY}');
                  var darkQuery = window.matchMedia('(prefers-color-scheme: dark)');

                  if (!initialTheme) {
                    initialTheme = darkQuery.matches ? 'DARK' : 'LIGHT';
                  }
                  setTheme(initialTheme);

                  darkQuery.addEventListener('change', function (e) {
                    preferredTheme = getCookieValue('${THEME_COOKIE_KEY}');
                    if (!preferredTheme) {
                      setTheme(e.matches ? 'DARK' : 'LIGHT');
                    }
                  });
                })();
              `
          }}
        />
      </body>
    </html>
  );
}

export default function App() {
  // we don't need persistence in DEV, because it might cause cache issues
  if (import.meta.env.DEV) {
    return (
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          <Outlet />
          <Toaster />
          <ReactQueryDevtools />
          <TailwindIndicator />
        </QueryClientProvider>
      </ThemeProvider>
    );
  }

  const persister = createSyncStoragePersister({
    storage: localStorage,
    throttleTime: import.meta.env.PROD
      ? durationToMs(30, "seconds")
      : durationToMs(3, "seconds"),
    retry: removeOldestQuery
  });

  return (
    <ThemeProvider>
      <PersistQueryClientProvider
        client={queryClient}
        persistOptions={{
          persister,
          maxAge: durationToMs(3, "days"),
          buster: __BUILD_ID__
        }}
      >
        <Outlet />
        <Toaster />
      </PersistQueryClientProvider>
    </ThemeProvider>
  );
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
        ? (error.data ?? "Looks like you're lost 😛")
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
