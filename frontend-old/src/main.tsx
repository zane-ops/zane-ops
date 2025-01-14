import {
  QueryClient,
  QueryClientProvider,
  keepPreviousData
} from "@tanstack/react-query";
import { RouterProvider, createRouter } from "@tanstack/react-router";
import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";

import { Loader } from "~/components/loader";
import { routeTree } from "./routeTree.gen";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      placeholderData: keepPreviousData,
      retry: 3
    }
  }
});

const router = createRouter({
  routeTree,
  defaultStaleTime: 3_600_000, // 1hr in milliseconds
  defaultPreload: "intent",
  defaultPendingComponent: () => <Loader />
});

const rootElement = document.getElementById("root")!;

if (!rootElement.innerHTML) {
  const root = ReactDOM.createRoot(rootElement);
  root.render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </React.StrictMode>
  );
}
