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

import {
  AlarmCheck,
  BookOpen,
  ChevronDown,
  ChevronsUpDown,
  CircleUser,
  Folder,
  Globe,
  Hammer,
  HeartHandshake,
  HelpCircle,
  LogOut,
  Search,
  Send,
  Settings,
  Twitter
} from "lucide-react";
import { useAuthUser } from "~/components/helper/use-auth-user";
import { Input } from "~/components/ui/input";

export const Route = createRootRoute({
  component: () => (
    <main className="bg-background">
      <Navigation />
      <Outlet />
      <Footer />
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
              <MenubarTrigger className="flex justify-center text-sm items-center gap-1">
                Create
                <ChevronsUpDown className="w-4" />
              </MenubarTrigger>
              <MenubarContent className="border min-w-6 border-border">
                <MenubarItem className="flex gap-5">
                  <Folder className="w-4 opacity-50" />
                  Project
                </MenubarItem>
                <MenubarItem className="flex gap-5">
                  <Globe className="w-4 opacity-50" />
                  Web Service
                </MenubarItem>
                <MenubarItem className="flex gap-5">
                  <Hammer className="w-4 opacity-50" />
                  Worker
                </MenubarItem>
                <MenubarItem className="flex gap-5">
                  <AlarmCheck className="w-4 opacity-50" />
                  CRON
                </MenubarItem>
              </MenubarContent>
            </MenubarMenu>
          </Menubar>
          <Search className="relative left-10" />
          <Input
            className="px-14 my-1 focus-visible:right-0"
            placeholder="Search for Service, Worker, CRON, etc..."
          />
          <HelpCircle className="w-16 stroke-[1.5px] opacity-70" />
        </div>

        <Menubar className="border-none w-fit">
          <MenubarMenu>
            <MenubarTrigger className="flex justify-center items-center gap-2">
              <CircleUser className="w-5 opacity-70" />
              <p>{user.username}</p>
              <ChevronDown className="w-4 my-auto" />
            </MenubarTrigger>
            <MenubarContent className="border min-w-0 mx-9  border-border">
              <MenubarItem className="flex gap-5">
                <Settings className="w-4 opacity-50" />
                Settings
              </MenubarItem>
              <MenubarItem className="flex gap-5">
                <LogOut className="w-4 opacity-50" />
                Logout
              </MenubarItem>
            </MenubarContent>
          </MenubarMenu>
        </Menubar>
      </header>
    </>
  );
}

const linksIconWidth = 15;
const links = [
  { name: "Feedback", url: "", icon: <Send width={linksIconWidth} /> },
  { name: "Docs", url: "", icon: <BookOpen width={linksIconWidth} /> },
  {
    name: "Contribute",
    url: "",
    icon: <HeartHandshake width={linksIconWidth} />
  },
  { name: "Twitter", url: "", icon: <Twitter width={linksIconWidth} /> }
];

function Footer() {
  return (
    <>
      <div className="h-[84vh]"></div>
      <div className="flex border-t border-opacity-65 border-border bg-toogle p-8 text-sm items-center gap-10">
        {links.map((link) => (
          <a className="flex underline items-center gap-2" href="">
            {link.icon}
            {link.name}
          </a>
        ))}
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
