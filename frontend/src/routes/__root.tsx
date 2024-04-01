import { Outlet, createRootRoute } from "@tanstack/react-router";
import { TanStackRouterDevtools } from "@tanstack/router-devtools";
import { Logo } from "~/components/logo";
import { MetaTitle } from "~/components/meta-title";
import { TailwindIndicator } from "~/components/tailwind-indicator";
import { Button } from "~/components/ui/button";
import {
  Menubar,
  MenubarContent,
  MenubarItem,
  MenubarMenu,
  MenubarTrigger
} from "~/components/ui/menubar";

import { Avatar, AvatarFallback, AvatarImage } from "~/components/ui/avatar";

import { ChevronDown, HelpCircle, Search } from "lucide-react";
import { useAuthUser } from "~/components/helper/use-auth-user";
import { Input } from "~/components/ui/input";

export const Route = createRootRoute({
  component: () => (
    <main className="bg-background h-screen">
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
      <header className="flex px-6 border-b border-opacity-65 border-border py-2 items-center bg-toogle t justify-between gap-4">
        <Logo className="w-10 flex-none h-10 mr-8" />
        <div className="flex  w-full items-center">
          <Menubar className="border-none w-fit text-black bg-primary">
            <MenubarMenu>
              <MenubarTrigger>Create</MenubarTrigger>
              <MenubarContent>
                <MenubarItem>Project</MenubarItem>
                <MenubarItem>Web Service</MenubarItem>
                <MenubarItem>Worker</MenubarItem>
                <MenubarItem>Cron</MenubarItem>
              </MenubarContent>
              <ChevronDown className="w-4" />
            </MenubarMenu>
          </Menubar>
          <Search className="relative left-10" />
          <Input
            className="px-14 my-1 focus-visible:right-0"
            placeholder="Search for Service, Worker, CRON, etc..."
          />
          <HelpCircle className="w-16 stroke-[1.5px] opacity-70" />
        </div>

        <div className="flex items-center gap-2">
          <Avatar className="w-8 h-8">
            <AvatarImage
              src="https://avatars.githubusercontent.com/u/38298743?v=4"
              alt={user.username}
            />

            <AvatarFallback>{user.username.substring(0, 2)}</AvatarFallback>
          </Avatar>
          <p>{user.username}</p>
          <ChevronDown className="w-4 my-auto" />
        </div>
      </header>
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
