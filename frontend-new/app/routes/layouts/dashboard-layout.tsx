import {
  BookOpen,
  ChevronDown,
  CircleUser,
  GitCommitVertical,
  HeartHandshake,
  HelpCircle,
  LogOut,
  Menu,
  Search,
  Send,
  TagIcon,
  Twitter
} from "lucide-react";
import { Link, Outlet, redirect, useFetcher } from "react-router";
import { Logo } from "~/components/logo";
import { Input } from "~/components/ui/input";
import {
  Menubar,
  MenubarContent,
  MenubarContentItem,
  MenubarMenu,
  MenubarTrigger
} from "~/components/ui/menubar";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetTrigger
} from "~/components/ui/sheet";
import { serverQueries, userQueries } from "~/lib/queries";
import { cn } from "~/lib/utils";
import { metaTitle } from "~/utils";

import { useQuery } from "@tanstack/react-query";
import * as React from "react";
import { NavigationProgress } from "~/components/navigation-progress";
import { Button } from "~/components/ui/button";
import { queryClient } from "~/root";
import type { Route } from "./+types/dashboard-layout";

export function meta() {
  return [metaTitle("Dashboard")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const userQuery = await queryClient.ensureQueryData(userQueries.authedUser);
  const user = userQuery.data?.user;

  if (!user) {
    let redirectPathName = `/login`;
    const url = new URL(request.url);
    if (url.pathname !== "/" && url.pathname !== "/login") {
      const params = new URLSearchParams([["redirect_to", url.pathname]]);
      redirectPathName = `/login?${params.toString()}`;
    }

    throw redirect(redirectPathName);
  }
  return user;
}

export default function DashboardLayout({ loaderData }: Route.ComponentProps) {
  return (
    <div className="min-h-screen flex flex-col justify-between">
      <NavigationProgress />
      <Header user={loaderData} />
      <main className="grow container p-6">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}

type HeaderProps = {
  user: Route.ComponentProps["loaderData"];
};

function Header({ user }: HeaderProps) {
  let fetcher = useFetcher();

  const isSheetOpen = React.useState(false);

  return (
    <>
      {!import.meta.env.PROD && (
        <div
          className={cn(
            "py-0.5 bg-red-500 text-white text-center fixed top-10 -left-10 -rotate-[30deg] z-100",
            "w-72"
          )}
        >
          <p className="">⚠️ YOU ARE IN DEV ⚠️</p>
        </div>
      )}
      <header className="flex px-6 border-b border-opacity-65 border-border py-2 items-center bg-toggle justify-between gap-4 sticky top-0 z-50">
        <Link to="/">
          <Logo className="w-10 flex-none h-10 mr-8" />
        </Link>
        <div className="md:flex hidden  w-full items-center">
          <Button asChild>
            <Link to="/create-project" prefetch="intent">
              Create project
            </Link>
          </Button>

          <div className="flex w-full justify-center items-center">
            <Search className="relative left-10" />
            <Input
              className="px-14 my-1  text-sm focus-visible:right-0"
              placeholder="Search for Service or Project"
            />
          </div>
          <a
            href="https://github.com/zane-ops/zane-ops"
            target="_blank"
            rel="noopener noreferrer"
          >
            <HelpCircle className="w-16 stroke-[1.5px] opacity-70" />
          </a>
        </div>

        <fetcher.Form
          method="post"
          action="/logout"
          id="logout-form"
          className="hidden"
        />
        <Menubar className="border-none md:block hidden w-fit">
          <MenubarMenu>
            <MenubarTrigger className="flex justify-center items-center gap-2">
              <CircleUser className="w-5 opacity-70" />
              <p>{user.username}</p>
              <ChevronDown className="w-4 my-auto" />
            </MenubarTrigger>
            <MenubarContent className="border min-w-0 mx-9  border-border">
              {/* <MenubarContentItem icon={Settings} text="Settings" /> */}
              <button
                className="w-full"
                onClick={(e) => {
                  e.currentTarget.form?.requestSubmit();
                }}
                form="logout-form"
                disabled={fetcher.state !== "idle"}
              >
                {fetcher.state !== "idle" ? (
                  "Logging out..."
                ) : (
                  <MenubarContentItem icon={LogOut} text="Logout" />
                )}
              </button>
            </MenubarContent>
          </MenubarMenu>
        </Menubar>

        {/** Mobile */}
        <div className="md:hidden block">
          <Sheet>
            <SheetTrigger>
              <Menu />
            </SheetTrigger>
            <SheetContent className="border flex rounded-xl  flex-col gap-5 w-full h-[calc(100dvh-100px)] border-border">
              <SheetHeader>
                <div className="absolute w-full top-3.5">
                  <div className="flex justify-between w-[78%] items-center">
                    <Link to="/">
                      <Logo className="w-10 flex-none h-10 mr-8" />
                    </Link>
                    <a
                      className="p-1 rounded-full border border-border "
                      href="https://github.com/zane-ops/zane-ops"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <HelpCircle className="h-6 w-6 opacity-70" />
                    </a>
                  </div>
                </div>
              </SheetHeader>
              <div className="flex mt-14 flex-col gap-3">
                <div className="flex  w-full mt-2 justify-center items-center">
                  <Input
                    className="my-1  placeholder:text-gray-400 text-sm focus-visible:right-0"
                    placeholder="Search for Service, Worker, CRON, etc..."
                  />
                  <Search className="absolute w-5 right-10" />
                </div>

                <div className="flex items-center  w-full">
                  <SheetClose asChild>
                    <Button
                      asChild
                      className="flex w-full justify-between text-sm items-center gap-1"
                    >
                      <Link to="/create-project">Create Project</Link>
                    </Button>
                  </SheetClose>
                </div>
              </div>

              <div className="flex justify-between px-2 py-5 items-center border-b border-border">
                <p>{user.username}</p>
                <CircleUser className="w-8 opacity-70" />
              </div>

              <SheetClose asChild>
                <button
                  type="submit"
                  form="logout-form"
                  className="p-2 rounded-md border border-card-foreground text-center"
                  disabled={fetcher.state !== "idle"}
                >
                  {fetcher.state !== "idle" ? (
                    "Logging out..."
                  ) : (
                    <div>Log Out</div>
                  )}
                </button>
              </SheetClose>
            </SheetContent>
          </Sheet>
        </div>
      </header>
    </>
  );
}

const socialLinks = [
  {
    name: "Feedback",
    url: "https://github.com/zane-ops/zane-ops/discussions",
    icon: <Send size={15} />
  },
  {
    name: "Docs",
    url: "https://zaneops.dev",
    icon: <BookOpen size={15} />
  },
  {
    name: "Contribute",
    url: "https://github.com/zane-ops/zane-ops/blob/main/CONTRIBUTING.md",
    icon: <HeartHandshake size={15} />
  },
  {
    name: "Twitter",
    url: "https://twitter.com/zaneopsdev",
    icon: <Twitter size={15} />
  }
];

function Footer() {
  const { data } = useQuery(serverQueries.settings);

  let image_version_url: string | null = null;
  if (data?.image_version === "canary") {
    image_version_url = "https://github.com/zane-ops/zane-ops/tree/main";
  } else if (data?.image_version.startsWith("pr-")) {
    image_version_url = `https://github.com/zane-ops/zane-ops/pull/${data.image_version.substring(3)}`;
  } else if (data?.image_version) {
    image_version_url = `https://github.com/zane-ops/zane-ops/tree/${data.image_version}`;
  }
  return (
    <>
      <footer className="flex flex-wrap justify-between border-t border-opacity-65 border-border bg-toggle p-8 text-sm gap-4 md:gap-10 ">
        <div className="items-center gap-4 md:gap-10 flex flex-wrap">
          {socialLinks.map((link) => (
            <a
              key={link.name}
              className="flex underline items-center gap-2"
              href={link.url}
              target="_blank"
            >
              {link.icon}
              {link.name}
            </a>
          ))}
        </div>
        {data && (
          <div className="flex gap-4">
            {data.commit_sha && (
              <span className="flex items-center gap-2">
                <GitCommitVertical size={15} />
                <span>
                  commit&nbsp;
                  <a
                    className="underline font-semibold"
                    href={`https://github.com/zane-ops/zane-ops/tree/${data.commit_sha}`}
                    target="_blank"
                  >
                    #{data.commit_sha.substring(0, 7)}
                  </a>
                </span>
              </span>
            )}
            {data.image_version && image_version_url && (
              <span className="flex items-center gap-2">
                <TagIcon size={15} />
                <span>
                  <a
                    className="underline font-semibold"
                    href={image_version_url}
                    target="_blank"
                  >
                    {data.image_version}
                  </a>
                </span>
              </span>
            )}
          </div>
        )}
      </footer>
    </>
  );
}
