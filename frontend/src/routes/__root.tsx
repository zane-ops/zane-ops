import { Outlet, createRootRoute } from "@tanstack/react-router";
import { TanStackRouterDevtools } from "@tanstack/router-devtools";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
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
    <div className="flex flex-col gap-5 h-screen items-center justify-center">
      <picture className="flex justify-center items-center">
        <source
          media="(prefers-color-scheme: dark)"
          srcSet="/logo/ZaneOps-SYMBOL-WHITE.svg"
        />
        <source
          media="(prefers-color-scheme: light)"
          srcSet="/logo/ZaneOps-SYMBOL-BLACK.svg"
        />
        <img
          src="/logo/ZaneOps-SYMBOL-BLACK.svg"
          alt="Zane logo"
          width={100}
          height={100}
        />
      </picture>
      <div className="flex-col flex items-center">
        <h1 className="text-3xl font-bold">Error 404</h1>
        <p>Looks like you're lost 😛</p>
      </div>
      <a href="/">
        {" "}
        <Button>Go home</Button>
      </a>
    </div>
  );
}
