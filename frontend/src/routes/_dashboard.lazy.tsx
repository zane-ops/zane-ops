import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Link,
  Outlet,
  createLazyFileRoute,
  useNavigate
} from "@tanstack/react-router";
import {
  AlarmCheck,
  BookOpen,
  ChevronDown,
  ChevronsUpDown,
  CircleUser,
  CommandIcon,
  Folder,
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
import * as React from "react";
import { apiClient } from "~/api/client";
import { Logo } from "~/components/logo";
import { Button } from "~/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandList,
  CommandSeparator
} from "~/components/ui/command";
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
import { deleteCookie, getCsrfTokenHeader } from "~/utils";

export const Route = createLazyFileRoute("/_dashboard")({
  component: () => (
    <div className="min-h-screen flex flex-col justify-between">
      <Header />
      <main className="flex-grow container p-6">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
});

function Header() {
  const query = useQuery(userQueries.authedUser);
  const navigate = useNavigate();
  const user = query.data?.data?.user;
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
      navigate({ to: "/login" });
      return null;
    }
  });

  if (!user) {
    return null;
  }
  return (
    <>
      <header className="flex px-6 border-b border-opacity-65 border-border py-2 items-center bg-toggle justify-between gap-4 sticky top-0 z-50">
        <Link to="/">
          <Logo className="w-10 flex-none h-10 mr-8" />
        </Link>
        <div className="md:flex hidden  w-full items-center">
          <Button asChild>
            <Link to="/create-project">Create project</Link>
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
                    <Link href="/">
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

const socialLinksIconWidth = 15;
const socialLinks = [
  {
    name: "Feedback",
    url: "https://github.com/zane-ops/zane-ops/discussions",
    icon: <Send width={socialLinksIconWidth} />
  },
  {
    name: "Docs",
    url: "https://zane.fredkiss.dev/docs",
    icon: <BookOpen width={socialLinksIconWidth} />
  },
  {
    name: "Contribute",
    url: "https://github.com/zane-ops/zane-ops/blob/main/CONTRIBUTING.md",
    icon: <HeartHandshake width={socialLinksIconWidth} />
  },
  {
    name: "Twitter",
    url: "https://twitter.com/zaneopsdev",
    icon: <Twitter width={socialLinksIconWidth} />
  }
];

function Footer() {
  return (
    <>
      <div className="flex border-t border-opacity-65 border-border bg-toggle p-8 text-sm items-center gap-4 md:gap-10">
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
    </>
  );
}

export function CommandMenu() {
  const [open, setOpen] = React.useState(false);
  const menuRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((prevOpen) => !prevOpen);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  return (
    <div className="relative w-full" ref={menuRef}>
      <div
        onClick={() => setOpen(true)}
        className="relative w-full flex items-center"
      >
        <Search size={15} className="absolute left-4 text-gray-400" />
        <Input
          className="w-full pl-12 pr-12 my-1 text-sm rounded-md border focus-visible:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Search for Service, Worker, CRON, etc..."
        />
        <div className="absolute bg-grey/20 right-4 px-2 py-1 rounded-md flex items-center space-x-1 ">
          <CommandIcon size={15} />
          <span className="text-xs">K</span>
        </div>
      </div>

      {open && (
        <div className="absolute top-12 left-0 w-full z-50 shadow-lg bg-white rounded-md">
          <Command>
            <CommandList>
              <CommandEmpty>No results found.</CommandEmpty>
              <CommandGroup heading="Suggestions">
                <CommandItem>Calendar</CommandItem>
                <CommandItem>Search Emoji</CommandItem>
                <CommandItem>Calculator</CommandItem>
              </CommandGroup>
              <CommandSeparator />
              <CommandGroup heading="Settings">
                <CommandItem>Profile</CommandItem>
                <CommandItem>Billing</CommandItem>
                <CommandItem>Settings</CommandItem>
              </CommandGroup>
            </CommandList>
          </Command>
        </div>
      )}
    </div>
  );
}
