import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Link,
  Outlet,
  createFileRoute,
  useNavigate
} from "@tanstack/react-router";
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
  Menu,
  Search,
  Send,
  Settings,
  Twitter
} from "lucide-react";
import { apiClient } from "~/api/client";
import { useAuthUser } from "~/components/helper/use-auth-user";
import { Logo } from "~/components/logo";
import { Input } from "~/components/ui/input";
import {
  Menubar,
  MenubarContent,
  MenubarItem,
  MenubarMenu,
  MenubarTrigger
} from "~/components/ui/menubar";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger
} from "~/components/ui/sheet";
import { userKeys } from "~/key-factories";
import { cn } from "~/lib/utils";
import { deleteCookie, getCookie } from "~/utils";

export const Route = createFileRoute("/_dashboard")({
  component: () => (
    <div className="min-h-screen flex flex-col justify-between">
      <Header />
      <main className="flex-grow  container p-6">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
});

function Header() {
  const query = useAuthUser();
  const navigate = useNavigate();
  const user = query.data?.data?.user;
  const queryClient = useQueryClient();
  const { data, isPending, mutate } = useMutation({
    mutationFn: async () => {
      // set csrf cookie token
      await apiClient.GET("/api/csrf/");
      const csrfToken = getCookie("csrftoken");
      const { error } = await apiClient.DELETE("/api/auth/logout/", {
        headers: {
          "X-CSRFToken": csrfToken
        }
      });
      if (error) {
        return error;
      }

      queryClient.removeQueries({
        queryKey: userKeys.authedUser
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
      <header className="flex px-6 border-b border-opacity-65 border-border py-2 items-center bg-toggle t justify-between gap-4">
        <Link href="/">
          <Logo className="w-10 flex-none h-10 mr-8" />
        </Link>
        <div className="md:flex hidden  w-full items-center">
          <Menubar className="border-none w-fit text-black bg-primary">
            <MenubarMenu>
              <MenubarTrigger className="flex  justify-center text-sm items-center gap-1">
                Create
                <ChevronsUpDown className="w-4" />
              </MenubarTrigger>
              <MenubarContent className=" border border-border min-w-6">
                <MenubarContentItem icon={Folder} text="Project" />
                <MenubarContentItem icon={Globe} text="Web Service" />
                <MenubarContentItem icon={Hammer} text="Worker" />
                <MenubarContentItem icon={AlarmCheck} text="CRON" />
              </MenubarContent>
            </MenubarMenu>
          </Menubar>
          <div className="flex w-full justify-center items-center">
            <Search className="relative left-10" />
            <Input
              className="px-14 my-1 placeholder:text-gray-400 text-sm focus-visible:right-0"
              placeholder="Search for Service, Worker, CRON, etc..."
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
              <Menu className="" />
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

                      <MenubarContent className=" border min-w-[22.7rem] border-border ">
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
                className="p-2 rounded-md border border-destructive-foreground text-center"
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

const linksIconWidth = 15;
const links = [
  {
    name: "Feedback",
    url: " https://github.com/zane-ops/zane-ops/discussions",
    icon: <Send width={linksIconWidth} />
  },
  {
    name: "Docs",
    url: "https://github.com/zane-ops/zane-ops/blob/main/docs.md",
    icon: <BookOpen width={linksIconWidth} />
  },
  {
    name: "Contribute",
    url: "https://github.com/zane-ops/zane-ops/blob/main/CONTRIBUTING.md",
    icon: <HeartHandshake width={linksIconWidth} />
  },
  {
    name: "Twitter",
    url: "https://twitter.com/zaneopsdev",
    icon: <Twitter width={linksIconWidth} />
  }
];

function Footer() {
  return (
    <>
      <div className="flex border-t border-opacity-65 border-border bg-toggle p-8 text-sm items-center gap-4 md:gap-10">
        {links.map((link) => (
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

type MenubarContentItemProps = {
  icon: React.ElementType;
  text: string;
  className?: string;
};

export function MenubarContentItem({
  icon: Icon,
  text,
  className
}: MenubarContentItemProps) {
  return (
    <MenubarItem
      className={cn("flex pr-4 w-full gap-2 cursor-pointer", className)}
    >
      {Icon && <Icon className={cn("w-4 opacity-50", className)} />}
      {text}
    </MenubarItem>
  );
}
