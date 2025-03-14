import {
  BookOpen,
  ChevronDown,
  ChevronRight,
  CircleUser,
  CommandIcon,
  GitCommitVertical,
  HeartHandshake,
  HeartIcon,
  HelpCircle,
  LogOut,
  Menu,
  Search,
  Send,
  TagIcon
} from "lucide-react";
import { Link, Outlet, redirect, useFetcher, useNavigate } from "react-router";
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
import { resourceQueries, serverQueries, userQueries } from "~/lib/queries";
import { cn } from "~/lib/utils";
import { metaTitle } from "~/utils";

import { useQuery } from "@tanstack/react-query";
import * as React from "react";
import { useDebounce } from "use-debounce";
import { NavigationProgress } from "~/components/navigation-progress";
import { Button } from "~/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList
} from "~/components/ui/command";
import { queryClient } from "~/root";
import type { Route } from "./+types/dashboard-layout";

export function meta() {
  return [metaTitle("Dashboard")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const [userQuery, userExistQuery] = await Promise.all([
    queryClient.ensureQueryData(userQueries.authedUser),
    queryClient.ensureQueryData(userQueries.checkUserExistence)
  ]);

  console.log({ exist: userExistQuery.data });

  if (!userExistQuery.data?.exists) {
    throw redirect("/onboarding");
  }

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
      <main
        className={cn("grow container p-6", !import.meta.env.PROD && "my-7")}
      >
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

  return (
    <>
      {!import.meta.env.PROD && (
        <div
          className={cn(
            "py-0.5 bg-red-500 text-white text-center fixed top-0 left-0 right-0  z-100",
            "w-full"
          )}
        >
          <p className="">⚠️ YOU ARE IN DEV ⚠️</p>
        </div>
      )}
      <header
        className={cn(
          "flex px-6 border-b border-opacity-65 border-border py-2 items-center bg-toggle justify-between gap-4 sticky top-0 z-60",
          !import.meta.env.PROD && "top-7"
        )}
      >
        <Link to="/">
          <Logo className="w-10 flex-none h-10 mr-8" />
        </Link>
        <div className="md:flex hidden  w-full items-center">
          <Button asChild>
            <Link to="/create-project" prefetch="intent">
              Create project
            </Link>
          </Button>

          <div className="flex mx-2 w-full justify-center items-center">
            <CommandMenu />
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
    name: "Docs",
    url: "https://zaneops.dev",
    icon: <BookOpen size={15} />
  },
  {
    name: "Feedback",
    url: "https://github.com/zane-ops/zane-ops/discussions",
    icon: <Send size={15} />
  },
  {
    name: "Contribute",
    url: "https://github.com/zane-ops/zane-ops/blob/main/CONTRIBUTING.md",
    icon: <HeartHandshake size={15} />
  },
  {
    name: "Sponsor this project",
    url: "https://github.com/sponsors/Fredkiss3",
    icon: <HeartIcon size={15} />
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

export function CommandMenu() {
  const [open, setOpen] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [resourceSearchQuery, setResourceSearchQuery] = React.useState("");
  const [debouncedValue] = useDebounce(resourceSearchQuery, 300);
  const navigate = useNavigate();

  const {
    data: resourceListData,
    isLoading,
    isFetching
  } = useQuery(resourceQueries.search(debouncedValue));

  React.useEffect(() => {
    const handleEvent = (e: KeyboardEvent | MouseEvent) => {
      if (
        e instanceof KeyboardEvent &&
        e.key === "k" &&
        (e.metaKey || e.ctrlKey)
      ) {
        e.preventDefault();
        setOpen((prev) => {
          const newState = !prev;
          if (newState) {
            inputRef.current?.focus();
          } else {
            inputRef.current?.blur();
          }
          return newState;
        });
      }

      if (
        e instanceof MouseEvent &&
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
        inputRef.current?.blur();
      }
    };

    document.addEventListener("keydown", handleEvent);
    document.addEventListener("mousedown", handleEvent);

    return () => {
      document.removeEventListener("keydown", handleEvent);
      document.removeEventListener("mousedown", handleEvent);
    };
  }, []);

  const resourceList = resourceListData?.data ?? [];
  const hideResultList =
    debouncedValue.trim().length === 0 || !open || isLoading || isFetching;

  return (
    <div ref={containerRef} className="relative w-full">
      <Command label="resources" shouldFilter={false}>
        <div className="relative w-full flex items-center">
          <Search size={15} className="absolute left-4 text-gray-400" />
          <CommandInput
            ref={inputRef}
            className="w-full pl-12 pr-12 m-0 text-sm rounded-md border"
            placeholder="Search for Service, Worker, CRON, etc..."
            name="resourceSearchQuery"
            value={resourceSearchQuery}
            onFocus={() => setOpen(true)}
            onValueChange={(value) => {
              setResourceSearchQuery(value);
              setOpen(true);
            }}
            onBlur={() => setOpen(false)}
          />
          <div className="absolute bg-grey/20 right-4 px-2 py-1 rounded-md flex items-center space-x-1">
            <CommandIcon size={15} />
            <span className="text-xs">K</span>
          </div>
        </div>

        <CommandList
          className={cn("absolute -top-1 left-0 w-full shadow-lg  rounded-md", {
            hidden: hideResultList
          })}
        >
          <CommandGroup
            heading={
              resourceList.length > 0 && (
                <span>Resources ({resourceList.length})</span>
              )
            }
          >
            <CommandEmpty>No results found.</CommandEmpty>
            {resourceList.map((resource) => (
              <CommandItem
                onSelect={() => {
                  const baseUrl = "/project";
                  const targetUrl =
                    resource.type === "project"
                      ? `${baseUrl}/${resource.slug}`
                      : `${baseUrl}/${resource.project_slug}/services/${resource.slug}`;
                  navigate(targetUrl);
                  setOpen(false);
                }}
                key={resource.id}
                className="block"
              >
                <p>{resource.slug}</p>
                <div className="text-link text-xs">
                  {resource.type === "project" ? (
                    "projects"
                  ) : (
                    <div className="flex gap-0.5 items-center">
                      <span className="flex-none">projects</span>{" "}
                      <ChevronRight size={13} />
                      <span>{resource.project_slug}</span>
                      <ChevronRight className="flex-none" size={13} />
                      <span className="flex-none">services</span>
                    </div>
                  )}
                </div>
              </CommandItem>
            ))}
          </CommandGroup>
        </CommandList>
      </Command>
    </div>
  );
}
