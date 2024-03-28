import { Outlet, createRootRoute } from "@tanstack/react-router";
import { TanStackRouterDevtools } from "@tanstack/router-devtools";
import { TailwindIndicator } from "~/components/tailwind-indicator";

export const Route = createRootRoute({
  component: () => (
    <main className="bg-background">
      <Outlet />
      <TailwindIndicator />
      <TanStackRouterDevtools />
    </main>
  ),
  notFoundComponent: () => (
    <p className="flex text-3xl h-screen items-center justify-center">
      404 You're lost what are you finding here thief
    </p>
  )
});
