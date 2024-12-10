import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlarmCheck,
  BookOpen,
  ChevronDown,
  ChevronsUpDown,
  CircleUser,
  Folder,
  GitCommitVertical,
  Globe,
  Hammer,
  HeartHandshake,
  HelpCircle,
  LogOut,
  Menu,
  Search,
  Send,
  Settings,
  Twitter
} from "lucide-react";
import { Link, Outlet, useNavigate } from "react-router";
import { apiClient } from "~/api/client";
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
  SheetContent,
  SheetHeader,
  SheetTrigger
} from "~/components/ui/sheet";
import { userQueries } from "~/lib/queries";
import { cn } from "~/lib/utils";
import { deleteCookie, getCsrfTokenHeader, metaTitle } from "~/utils";

import { NavigationProgress } from "~/components/navigation-progress";
import { Button } from "~/components/ui/button";
import { ensureAuthedUser } from "~/lib/ensure-authed-user";
import type { Route } from "./+types/dashboard-layout";

export function meta() {
  return [metaTitle("Dashboard")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader() {
  return await ensureAuthedUser();
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
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { isPending, mutate } = useMutation({
    mutationFn: async () => {
      const { error } = await apiClient.DELETE("/api/auth/logout/", {
        headers: {
          ...(await getCsrfTokenHeader())
        }
      });
      if (error) {
        return error;
      }

      queryClient.removeQueries({
        queryKey: userQueries.authedUser.queryKey
      });
      deleteCookie("csrftoken");
      navigate("/login");
      return null;
    }
  });

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

        <Menubar className="border-none md:block hidden w-fit">
          <MenubarMenu>
            <MenubarTrigger className="flex justify-center items-center gap-2">
              <CircleUser className="w-5 opacity-70" />
              <p>{user.username}</p>
              <ChevronDown className="w-4 my-auto" />
            </MenubarTrigger>
            <MenubarContent className="border min-w-0 mx-9  border-border">
              <MenubarContentItem icon={Settings} text="Settings" />
              <button
                onClick={() => mutate()}
                className="w-full"
                disabled={isPending}
              >
                {isPending ? (
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
                  <Menubar className="border-none w-full text-black bg-primary">
                    <MenubarMenu>
                      <MenubarTrigger className="flex w-full justify-between text-sm items-center gap-1">
                        Create
                        <ChevronsUpDown className="w-4" />
                      </MenubarTrigger>

                      <MenubarContent className=" border w-[calc(var(--radix-menubar-trigger-width)+0.5rem)] border-border ">
                        <MenubarContentItem icon={Folder} text="Project" />
                        <MenubarContentItem icon={Globe} text="Web Service" />
                        <MenubarContentItem icon={Hammer} text="Worker" />
                        <MenubarContentItem icon={AlarmCheck} text="CRON" />
                      </MenubarContent>
                    </MenubarMenu>
                  </Menubar>
                </div>
              </div>

              <div className="flex justify-between px-2 py-5 items-center border-b border-border">
                <p>{user.username}</p>
                <CircleUser className="w-8 opacity-70" />
              </div>

              <button
                className="p-2 rounded-md border border-card-foreground text-center"
                onClick={() => mutate()}
                disabled={isPending}
              >
                {isPending ? "Logging out..." : <div>Log Out</div>}
              </button>
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
              rel="noopener noreferrer"
            >
              {link.icon}
              {link.name}
            </a>
          ))}
        </div>
        {import.meta.env.VITE_COMMIT_SHA && (
          <a
            className="flex underline items-center gap-2"
            href={`https://github.com/zane-ops/zane-ops/tree/${import.meta.env.VITE_COMMIT_SHA}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            <GitCommitVertical size={15} />
            commit #{import.meta.env.VITE_COMMIT_SHA.substring(0, 7)}
          </a>
        )}
      </footer>
    </>
  );
}
