import { Outlet, createRootRoute } from "@tanstack/react-router";
import { TanStackRouterDevtools } from "@tanstack/router-devtools";
import { Logo } from "~/components/logo";
import { MetaTitle } from "~/components/meta-title";
import { TailwindIndicator } from "~/components/tailwind-indicator";
import { Button } from "~/components/ui/button";

export const Route = createRootRoute({
  component: () => (
    <div className="bg-background">
      <Outlet />
      <TailwindIndicator />
      <TanStackRouterDevtools />
    </div>
  ),
  notFoundComponent: NotFound
});

function NotFound() {
  return (
    <>
      <MetaTitle title="404 - page not found" />
      <div className="flex flex-col gap-5 h-screen items-center justify-center">
        <Logo className="md:flex" />
        <div className="flex-col flex gap-3 items-center">
          <h1 className="text-3xl font-bold">Error 404</h1>
          <p className="text-lg">Looks like you're lost 😛</p>
        </div>
        <a href="/">
          <Button>Go home</Button>
        </a>
      </div>
    </>
  );
}
