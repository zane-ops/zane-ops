import { Outlet, createFileRoute } from "@tanstack/react-router";
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
import { Logo } from "~/components/logo";
import { Input } from "~/components/ui/input";
import {
  Menubar,
  MenubarContent,
  MenubarItem,
  MenubarMenu,
  MenubarTrigger
} from "~/components/ui/menubar";
import { cn } from "~/lib/utils";

export const Route = createFileRoute("/_layout")({
  component: () => (
    <div>
      <Header />
      <main>
        <Outlet />
      </main>
      <Footer />
    </div>
  )
});

function Header() {
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
              <MenubarContent className="border pr-4 min-w-6 border-border">
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
              className="px-14 my-1 text-sm focus-visible:right-0"
              placeholder="Search for Service, Worker, CRON, etc..."
            />
          </div>
          <HelpCircle className="w-16 stroke-[1.5px] opacity-70" />
        </div>

        <Menubar className="border-none w-fit">
          <MenubarMenu>
            <MenubarTrigger className="flex justify-center items-center gap-2">
              <CircleUser className="w-5 opacity-70" />
              <p>{user.username}</p>
              <ChevronDown className="w-4 my-auto" />
            </MenubarTrigger>
            <MenubarContent className="border pr-4 min-w-0 mx-9  border-border">
              <MenubarContentItem icon={Settings} text="Settings" />
              <MenubarContentItem icon={LogOut} text="Logout" />
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
          <a
            key={link.name}
            className="flex underline items-center gap-2"
            href=""
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

function MenubarContentItem({
  icon: Icon,
  text,
  className
}: MenubarContentItemProps) {
  return (
    <MenubarItem className={cn("flex gap-2", className)}>
      {Icon && <Icon className={cn("w-4 opacity-50", className)} />}
      {text}
    </MenubarItem>
  );
}
