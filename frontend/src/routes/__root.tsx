import { Outlet, createRootRoute } from "@tanstack/react-router";
import { TanStackRouterDevtools } from "@tanstack/router-devtools";
import { Logo } from "~/components/logo";
import { MetaTitle } from "~/components/meta-title";
import { TailwindIndicator } from "~/components/tailwind-indicator";
import { Button } from "~/components/ui/button";

import { Avatar, AvatarFallback, AvatarImage } from "~/components/ui/avatar";

import { useAuthUser } from "~/components/helper/use-auth-user";
import { Command, CommandInput } from "~/components/ui/command";
import { Input } from "~/components/ui/input";

export const Route = createRootRoute({
  component: () => (
    <main className="bg-background h-[100vh]">
      <Navigation />
      <Outlet />
      <TailwindIndicator />
      <TanStackRouterDevtools />
    </main>
  ),
  notFoundComponent: NotFound
});

function Navigation() {
  const query = useAuthUser();
  const user = query.data?.data?.user;
  if (!user) {
    return null;
  }

  return (
    <>
      <div className="flex justify-between px-10 items-center p-2 gap-">
        <Logo />
        <Input className="text-center w-[80%]" placeholder="Search something" />
        <Avatar>
          <AvatarImage
            src="https://avatars.githubusercontent.com/u/38298743?v=4"
            alt="@shadcn"
          />
          <AvatarFallback>{user.username.substring(0, 2)}</AvatarFallback>
        </Avatar>
      </div>
    </>
  );
}

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
