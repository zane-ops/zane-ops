import { Outlet, createRootRoute } from "@tanstack/react-router";
import { TanStackRouterDevtools } from "@tanstack/router-devtools";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import { Logo } from "~/components/logo";
import { TailwindIndicator } from "~/components/tailwind-indicator";
import { Button } from "~/components/ui/button";

export const Route = createRootRoute({
  component: () => (
    <main className="bg-background">
      <Outlet />
      <TailwindIndicator />
      <TanStackRouterDevtools />
    </main>
  ),
  notFoundComponent: withAuthRedirect(NotFound)
});

function NotFound() {
  return (
    <>
      <title>404 - page not found | ZaneOps</title>
      <div className="flex flex-col gap-5 h-screen items-center justify-center">
        <Logo className="flex" />
        <div className="flex-col flex items-center">
          <h1 className="text-3xl font-bold">Error 404</h1>
          <p>Looks like you're lost 😛</p>
        </div>
        <a href="/">
          {" "}
          <Button>Go home</Button>
        </a>
      </div>
    </>
  );
}
