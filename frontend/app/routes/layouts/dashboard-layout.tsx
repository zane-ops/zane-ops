import {
  ArrowBigUpDash,
  BookOpen,
  ChevronDown,
  ChevronRight,
  CircleUser,
  CommandIcon,
  ContainerIcon,
  FolderIcon,
  GitCommitVertical,
  GithubIcon,
  GitlabIcon,
  HeartHandshake,
  HeartIcon,
  LaptopMinimalIcon,
  LoaderIcon,
  LogOut,
  Menu,
  MoonIcon,
  NetworkIcon,
  Search,
  SettingsIcon,
  Sparkles,
  SunIcon,
  TagIcon
} from "lucide-react";
import {
  Link,
  Outlet,
  href,
  redirect,
  useFetcher,
  useNavigate
} from "react-router";
import { ThemedLogo } from "~/components/logo";
import { Input } from "~/components/ui/input";
import {
  Menubar,
  MenubarContent,
  MenubarContentItem,
  MenubarMenu,
  MenubarSeparator,
  MenubarTrigger
} from "~/components/ui/menubar";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetTrigger
} from "~/components/ui/sheet";
import {
  resourceQueries,
  serverQueries,
  userQueries,
  versionQueries
} from "~/lib/queries";
import { cn } from "~/lib/utils";
import { metaTitle } from "~/utils";

import { useQuery } from "@tanstack/react-query";
import * as React from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast } from "sonner";
import { useDebounce } from "use-debounce";
import { NavigationProgress } from "~/components/navigation-progress";
import { StatusBadge } from "~/components/status-badge";
import { type Theme, useTheme } from "~/components/theme-provider";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList
} from "~/components/ui/command";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "~/components/ui/dialog";
import { ToggleGroup, ToggleGroupItem } from "~/components/ui/toggle-group";
import { queryClient } from "~/root";
import type { clientAction } from "~/routes/trigger-update";
import type { Route } from "./+types/dashboard-layout";

export function meta() {
  return [metaTitle("Dashboard")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const [user, userExistQuery] = await Promise.all([
    queryClient.ensureQueryData(userQueries.authedUser),
    queryClient.ensureQueryData(userQueries.checkUserExistence)
  ]);

  if (!userExistQuery.data?.exists) {
    throw redirect("/onboarding");
  }

  if (!user) {
    let redirectPathName = `/login`;
    const url = new URL(request.url);
    if (url.pathname !== "/" && url.pathname !== "/login") {
      const params = new URLSearchParams([["redirect_to", url.pathname]]);
      redirectPathName = `/login?${params.toString()}`;
    }

    throw redirect(redirectPathName);
  }
  return { user };
}

export default function DashboardLayout({ loaderData }: Route.ComponentProps) {
  const [showUpdateDialog, setshowUpdateDialog] = React.useState(false);
  const fetcher = useFetcher<typeof clientAction>();
  const isPending = fetcher.state !== "idle";

  React.useEffect(() => {
    if (fetcher.state === "idle" && fetcher.data?.data) {
      setshowUpdateDialog(false);
    }
  }, [fetcher.data, fetcher.state]);

  const { data: latestVersion } = useQuery(versionQueries.latest);
  const { data: serverSettings } = useQuery(serverQueries.settings);

  const previousVersion = serverSettings?.image_version;

  React.useEffect(() => {
    if (
      import.meta.env.PROD &&
      latestVersion?.tag &&
      previousVersion &&
      previousVersion !== "canary" && // ignore canary as it is the latest version
      !previousVersion.startsWith("pr-") && // ignore pr branch versions
      previousVersion !== latestVersion.tag
    ) {
      toast.success("New version of ZaneOps available !", {
        description: latestVersion.tag,
        closeButton: true,
        duration: Number.POSITIVE_INFINITY,
        id: "new-version-available",
        icon: <Sparkles size={17} />,
        action: (
          <Button
            onClick={() => {
              setshowUpdateDialog(true);
              toast.dismiss("new-version-available");
            }}
            className="text-xs cursor-pointer"
            size="xs"
          >
            Inspect
          </Button>
        ),
        style: {
          flex: "row",
          justifyContent: "space-between"
        }
      });
    }
  }, [previousVersion, latestVersion?.tag]);

  const { data: user } = useQuery({
    ...userQueries.authedUser,
    initialData: loaderData.user
  });

  if (!user) return null;

  return (
    <div className="min-h-screen flex flex-col justify-between">
      <NavigationProgress />
      <Header user={user} />
      <main
        className={cn(
          "grow container p-6 relative",
          !import.meta.env.PROD && "my-7"
        )}
      >
        <Outlet />
        {latestVersion && (
          <Dialog open={showUpdateDialog} onOpenChange={setshowUpdateDialog}>
            <DialogContent className="sm:max-w-[525px]">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2 pb-3">
                  <span>New Version Available</span>
                  <StatusBadge color="blue" className="flex items-center gap-1">
                    {latestVersion.tag}
                  </StatusBadge>
                </DialogTitle>
                <DialogDescription className="border-t border-border -mx-6 px-6 pt-2">
                  <p className="text-start text-lg font-medium">
                    Release notes:
                  </p>
                  <div className="flex my-2 flex-col gap-2.5 markdown py-2 rounded-lg bg-muted p-4">
                    <Markdown remarkPlugins={[remarkGfm]}>
                      {latestVersion.body}
                    </Markdown>
                  </div>
                </DialogDescription>
              </DialogHeader>

              <DialogFooter className="flex flex-col md:flex-row flex-wrap gap-3 -mx-6 pt-6 px-6 border-t border-border">
                <fetcher.Form
                  action="/trigger-update"
                  method="POST"
                  className="order-1 md:order-1 w-full md:w-auto"
                >
                  <input
                    type="hidden"
                    name="desired_version"
                    value={latestVersion.tag}
                  />
                  <SubmitButton
                    isPending={isPending}
                    className="flex gap-1 items-center w-full md:w-fit"
                    onClick={() => setshowUpdateDialog(false)}
                  >
                    {isPending ? (
                      <>
                        <span>Updating...</span>
                        <LoaderIcon className="animate-spin" size={15} />
                      </>
                    ) : (
                      <>
                        <span>Update ZaneOps</span>
                        <ArrowBigUpDash size={15} />
                      </>
                    )}
                  </SubmitButton>
                </fetcher.Form>

                <Button
                  variant="outline"
                  onClick={() => setshowUpdateDialog(false)}
                  className="order-2 md:order-2 w-full md:w-auto"
                >
                  Cancel
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}
      </main>
      <Footer />
    </div>
  );
}

type HeaderProps = {
  user: Route.ComponentProps["loaderData"]["user"];
};

function Header({ user }: HeaderProps) {
  const fetcher = useFetcher();
  const navigate = useNavigate();

  // const { setTheme, theme } = useTheme();

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
          <ThemedLogo className="flex-none size-10 mr-8" />
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
              <MenubarContentItem
                icon={SettingsIcon}
                text="Settings"
                onClick={() => {
                  navigate("/settings");
                }}
              />

              <MenubarSeparator />
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
                  <MenubarContentItem
                    icon={LogOut}
                    text="Logout"
                    className="text-red-400"
                  />
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
                      <ThemedLogo className="w-10 flex-none h-10 mr-8" />
                    </Link>
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

export const Discord = () => (
  <svg
    width="15px"
    height="15px"
    viewBox="0 0 15 15"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      d="M11.5 13.5L11.1737 13.8788C11.2686 13.9606 11.3907 14.0037 11.5158 13.9997L11.5 13.5ZM10.4335 11.7878C10.2624 11.5711 9.94794 11.5341 9.73121 11.7052C9.51447 11.8763 9.4775 12.1907 9.64861 12.4075L10.4335 11.7878ZM10.8322 11.3784L10.6582 10.9096C10.6516 10.9121 10.645 10.9147 10.6385 10.9174L10.8322 11.3784ZM9.09418 11.8939L9.01021 11.4009L9.00204 11.4024L9.09418 11.8939ZM5.98973 11.8819L5.89494 12.3728L5.89798 12.3734L5.98973 11.8819ZM4.22774 11.3665L4.04551 11.8321L4.04599 11.8323L4.22774 11.3665ZM3.35265 10.959L3.07465 11.3745C3.08562 11.3819 3.09688 11.3888 3.10839 11.3952L3.35265 10.959ZM3.24482 10.899L3.52239 10.4831C3.50507 10.4715 3.48705 10.4611 3.46843 10.4518L3.24482 10.899ZM3.19689 10.8631L3.55044 10.5095C3.5176 10.4767 3.48034 10.4486 3.43974 10.426L3.19689 10.8631ZM5.35136 12.3834C5.52244 12.1666 5.4854 11.8522 5.26863 11.6811C5.05186 11.5101 4.73746 11.5471 4.56638 11.7639L5.35136 12.3834ZM3.5 13.5L3.48417 13.9997C3.61147 14.0038 3.7355 13.9591 3.83096 13.8748L3.5 13.5ZM0.5 11.2466H0C0 11.2734 0.00214589 11.3001 0.00641701 11.3265L0.5 11.2466ZM2.22601 2.75854L1.92601 2.35854C1.84944 2.41597 1.79097 2.49416 1.75753 2.58383L2.22601 2.75854ZM5.59413 1.49998L6.09188 1.45257C6.06784 1.20012 5.85861 1.00565 5.60508 1.0001L5.59413 1.49998ZM5.21626 2.80603C5.24244 3.08092 5.48652 3.28255 5.76142 3.25637C6.03631 3.23019 6.23794 2.98611 6.21176 2.71121L5.21626 2.80603ZM8.74205 2.74286C8.70687 3.01675 8.90039 3.2673 9.17428 3.30248C9.44817 3.33766 9.69872 3.14414 9.7339 2.87025L8.74205 2.74286ZM9.40578 1.50006L9.39481 1.00018C9.14752 1.00561 8.94137 1.19103 8.90986 1.43636L9.40578 1.50006ZM12.7739 2.75862L13.2424 2.58391C13.2089 2.49424 13.1505 2.41605 13.0739 2.35863L12.7739 2.75862ZM14.5 11.2466L14.9936 11.3265C14.9979 11.3001 15 11.2734 15 11.2466H14.5ZM6.48111 8.80137L5.98111 8.79314V8.80137H6.48111ZM11.5 13.5C11.8263 13.1212 11.8263 13.1212 11.8263 13.1212C11.8263 13.1212 11.8263 13.1212 11.8263 13.1212C11.8263 13.1211 11.8263 13.1211 11.8262 13.1211C11.8261 13.121 11.826 13.1209 11.8257 13.1207C11.8253 13.1203 11.8246 13.1197 11.8236 13.1188C11.8217 13.1172 11.8187 13.1146 11.8148 13.1112C11.807 13.1045 11.7954 13.0944 11.7804 13.0813C11.7503 13.0552 11.7068 13.0171 11.6534 12.97C11.5464 12.8756 11.4004 12.7453 11.2436 12.6013C10.9188 12.3032 10.5844 11.9789 10.4335 11.7878L9.64861 12.4075C9.85733 12.6718 10.2524 13.0488 10.5672 13.3379C10.7302 13.4876 10.8814 13.6225 10.9918 13.7199C11.0471 13.7686 11.0923 13.8081 11.1238 13.8355C11.1395 13.8493 11.1518 13.86 11.1603 13.8673C11.1645 13.8709 11.1678 13.8738 11.1701 13.8757C11.1712 13.8767 11.1721 13.8774 11.1727 13.878C11.173 13.8782 11.1732 13.8784 11.1734 13.8786C11.1735 13.8786 11.1735 13.8787 11.1736 13.8788C11.1736 13.8788 11.1736 13.8788 11.1737 13.8788C11.1737 13.8788 11.1737 13.8788 11.5 13.5ZM11.9356 10.2537C11.4758 10.5565 11.0422 10.7671 10.6582 10.9096L11.0061 11.8472C11.4611 11.6783 11.9625 11.4334 12.4856 11.0889L11.9356 10.2537ZM10.6385 10.9174C10.0719 11.1555 9.53331 11.3119 9.01022 11.401L9.17813 12.3868C9.78168 12.284 10.3938 12.1049 11.0258 11.8394L10.6385 10.9174ZM9.00204 11.4024C7.92329 11.6047 6.93198 11.5492 6.08148 11.3904L5.89798 12.3734C6.84535 12.5503 7.9636 12.6145 9.18631 12.3853L9.00204 11.4024ZM6.08451 11.391C5.43771 11.2661 4.87997 11.0843 4.4095 10.9007L4.04599 11.8323C4.55827 12.0322 5.17519 12.2339 5.89494 12.3728L6.08451 11.391ZM4.40998 10.9009C4.14799 10.7984 3.87062 10.6759 3.59691 10.5227L3.10839 11.3952C3.43414 11.5776 3.75606 11.7188 4.04551 11.8321L4.40998 10.9009ZM3.63066 10.5434C3.58272 10.5113 3.53734 10.4892 3.52248 10.4818C3.50124 10.4712 3.51056 10.4752 3.52239 10.4831L2.96725 11.3149C3.01506 11.3468 3.06035 11.3688 3.07506 11.3761C3.09615 11.3867 3.0867 11.3826 3.07465 11.3745L3.63066 10.5434ZM3.46843 10.4518C3.48779 10.4614 3.50836 10.4744 3.5282 10.4902C3.54528 10.5038 3.55731 10.5164 3.55044 10.5095L2.84334 11.2166C2.86645 11.2398 2.92415 11.2977 3.02122 11.3462L3.46843 10.4518ZM3.43974 10.426C3.34075 10.371 3.26491 10.3249 3.21518 10.2935C3.19033 10.2778 3.17205 10.2658 3.16072 10.2583C3.15505 10.2545 3.15113 10.2518 3.14899 10.2504C3.14792 10.2496 3.1473 10.2492 3.14713 10.2491C3.14704 10.249 3.14707 10.249 3.14722 10.2491C3.14729 10.2492 3.14739 10.2493 3.14752 10.2494C3.14758 10.2494 3.14765 10.2494 3.14773 10.2495C3.14777 10.2495 3.14781 10.2496 3.14785 10.2496C3.14787 10.2496 3.14791 10.2496 3.14792 10.2496C3.14795 10.2497 3.14799 10.2497 2.86127 10.6593C2.57456 11.0689 2.5746 11.069 2.57463 11.069C2.57464 11.069 2.57468 11.069 2.57471 11.069C2.57476 11.0691 2.57481 11.0691 2.57486 11.0691C2.57497 11.0692 2.57508 11.0693 2.57521 11.0694C2.57545 11.0696 2.57573 11.0698 2.57603 11.07C2.57664 11.0704 2.57737 11.0709 2.57822 11.0715C2.57991 11.0727 2.58207 11.0741 2.5847 11.0759C2.58996 11.0795 2.59709 11.0844 2.60603 11.0903C2.62392 11.1022 2.64909 11.1187 2.68118 11.139C2.74532 11.1795 2.83729 11.2353 2.95404 11.3002L3.43974 10.426ZM4.56638 11.7639C4.41376 11.9573 4.07727 12.2887 3.75273 12.5928C3.59569 12.74 3.44941 12.8734 3.34231 12.9701C3.28881 13.0184 3.24523 13.0574 3.21514 13.0842C3.2001 13.0977 3.18844 13.108 3.1806 13.115C3.17668 13.1184 3.17372 13.1211 3.17178 13.1228C3.1708 13.1237 3.17008 13.1243 3.16963 13.1247C3.1694 13.1249 3.16923 13.125 3.16913 13.1251C3.16908 13.1252 3.16905 13.1252 3.16903 13.1252C3.16903 13.1252 3.16903 13.1252 3.16902 13.1252C3.16903 13.1252 3.16904 13.1252 3.5 13.5C3.83096 13.8748 3.83098 13.8748 3.831 13.8748C3.83101 13.8747 3.83104 13.8747 3.83107 13.8747C3.83112 13.8746 3.83118 13.8746 3.83127 13.8745C3.83144 13.8744 3.83167 13.8742 3.83197 13.8739C3.83257 13.8734 3.83343 13.8726 3.83455 13.8716C3.83679 13.8696 3.84004 13.8667 3.84427 13.863C3.85271 13.8555 3.86502 13.8446 3.88074 13.8306C3.91217 13.8025 3.95728 13.7621 4.01247 13.7123C4.12273 13.6127 4.27376 13.475 4.43649 13.3225C4.75149 13.0273 5.14444 12.6456 5.35136 12.3834L4.56638 11.7639ZM3.51583 13.0003C2.35017 12.9633 1.73777 12.4789 1.40514 12.0399C1.23257 11.8121 1.12759 11.5854 1.06623 11.4163C1.03573 11.3323 1.01659 11.2641 1.00552 11.2195C0.999995 11.1973 0.996522 11.1811 0.994669 11.1719C0.993743 11.1673 0.993226 11.1645 0.993063 11.1636C0.992981 11.1632 0.992988 11.1632 0.993077 11.1637C0.993121 11.164 0.993186 11.1644 0.993271 11.1649C0.993313 11.1651 0.993361 11.1654 0.993413 11.1657C0.993439 11.1659 0.993481 11.1662 0.993494 11.1662C0.993538 11.1665 0.993583 11.1668 0.5 11.2466C0.00641701 11.3265 0.00646466 11.3268 0.00651383 11.3271C0.0065321 11.3272 0.00658301 11.3275 0.00661978 11.3277C0.00669345 11.3282 0.00677329 11.3287 0.00685936 11.3292C0.00703153 11.3302 0.00722873 11.3314 0.00745201 11.3327C0.00789851 11.3353 0.00844941 11.3384 0.00911263 11.3421C0.0104389 11.3494 0.0122158 11.3588 0.0145077 11.3701C0.0190892 11.3928 0.0257432 11.4233 0.0349903 11.4605C0.0534559 11.5349 0.0824359 11.6369 0.126228 11.7575C0.213456 11.9978 0.361783 12.3187 0.608079 12.6438C1.11319 13.3105 2.0008 13.9528 3.48417 13.9997L3.51583 13.0003ZM1 11.2466C1 9.38039 1.41906 7.30679 1.84654 5.6825C2.0593 4.87407 2.2721 4.1845 2.4315 3.69763C2.51117 3.4543 2.5774 3.26191 2.62349 3.13095C2.64653 3.06548 2.66453 3.01539 2.67665 2.98199C2.68271 2.9653 2.68729 2.95278 2.6903 2.94459C2.69181 2.9405 2.69292 2.9375 2.69362 2.9356C2.69397 2.93465 2.69423 2.93398 2.69437 2.93358C2.69444 2.93339 2.69449 2.93326 2.69451 2.9332C2.69452 2.93317 2.69452 2.93318 2.69453 2.93317C2.69452 2.93319 2.6945 2.93324 2.22601 2.75854C1.75753 2.58383 1.7575 2.58392 1.75746 2.58401C1.75744 2.58407 1.7574 2.58418 1.75735 2.5843C1.75727 2.58452 1.75716 2.58482 1.75703 2.58518C1.75675 2.58591 1.75638 2.58692 1.7559 2.58821C1.75495 2.59079 1.75358 2.59449 1.75182 2.59927C1.7483 2.60884 1.74319 2.62278 1.73661 2.64093C1.72344 2.67722 1.70436 2.73034 1.68021 2.79896C1.6319 2.93621 1.56329 3.13557 1.48114 3.38647C1.31692 3.88805 1.09821 4.59684 0.879472 5.42799C0.443946 7.08285 0 9.2533 0 11.2466H1ZM2.52602 3.15854C3.32548 2.55893 4.10267 2.26942 4.67586 2.12956C4.96251 2.05961 5.19735 2.0273 5.35697 2.01243C5.43671 2.005 5.49744 2.00194 5.5362 2.0007C5.55557 2.00008 5.56942 1.99992 5.57738 1.99989C5.58136 1.99987 5.58387 1.99988 5.58485 1.99989C5.58534 1.9999 5.58545 1.9999 5.58518 1.9999C5.58504 1.99989 5.58481 1.99989 5.58447 1.99988C5.58431 1.99988 5.58412 1.99988 5.5839 1.99987C5.58379 1.99987 5.58361 1.99987 5.58356 1.99987C5.58338 1.99986 5.58318 1.99986 5.59413 1.49998C5.60508 1.0001 5.60488 1.00009 5.60467 1.00009C5.60459 1.00009 5.60437 1.00008 5.60422 1.00008C5.6039 1.00007 5.60356 1.00007 5.60319 1.00006C5.60246 1.00005 5.60163 1.00003 5.6007 1.00002C5.59883 0.999988 5.59656 0.999958 5.59389 0.999934C5.58855 0.999886 5.58163 0.999858 5.57316 0.999894C5.55622 0.999966 5.53311 1.00029 5.50421 1.00122C5.44642 1.00307 5.36538 1.00731 5.2642 1.01674C5.06199 1.03558 4.77843 1.07519 4.4388 1.15806C3.75943 1.32384 2.85256 1.66361 1.92601 2.35854L2.52602 3.15854ZM5.09639 1.54738L5.21626 2.80603L6.21176 2.71121L6.09188 1.45257L5.09639 1.54738ZM9.7339 2.87025L9.90171 1.56376L8.90986 1.43636L8.74205 2.74286L9.7339 2.87025ZM9.40578 1.50006C9.41676 1.99994 9.41656 1.99994 9.41638 1.99995C9.41633 1.99995 9.41615 1.99995 9.41604 1.99995C9.41582 1.99996 9.41563 1.99996 9.41547 1.99997C9.41513 1.99997 9.4149 1.99998 9.41476 1.99998C9.41448 1.99998 9.4146 1.99998 9.41509 1.99998C9.41607 1.99997 9.41858 1.99995 9.42256 1.99997C9.43052 2 9.44437 2.00016 9.46374 2.00078C9.5025 2.00202 9.56323 2.00507 9.64297 2.0125C9.80258 2.02737 10.0374 2.05967 10.3241 2.12961C10.8972 2.26947 11.6744 2.55897 12.4739 3.15861L13.0739 2.35863C12.1474 1.66366 11.2405 1.32388 10.5611 1.15811C10.2215 1.07524 9.93791 1.03564 9.73569 1.01681C9.63452 1.00739 9.55347 1.00314 9.49568 1.00129C9.46678 1.00037 9.44367 1.00005 9.42673 0.999975C9.41827 0.99994 9.41134 0.999968 9.406 1.00002C9.40333 1.00004 9.40106 1.00007 9.3992 1.0001C9.39826 1.00011 9.39743 1.00013 9.3967 1.00014C9.39633 1.00015 9.39599 1.00016 9.39568 1.00016C9.39552 1.00016 9.3953 1.00017 9.39522 1.00017C9.39501 1.00018 9.39481 1.00018 9.40578 1.50006ZM12.7739 2.75862C12.3054 2.93333 12.3054 2.93329 12.3054 2.93326C12.3054 2.93327 12.3054 2.93326 12.3054 2.93329C12.3054 2.93335 12.3055 2.93348 12.3055 2.93367C12.3057 2.93407 12.3059 2.93474 12.3063 2.93569C12.307 2.93759 12.3081 2.9406 12.3096 2.94469C12.3126 2.95287 12.3172 2.96539 12.3233 2.98209C12.3354 3.01548 12.3534 3.06557 12.3764 3.13104C12.4225 3.26199 12.4888 3.45438 12.5684 3.6977C12.7278 4.18458 12.9406 4.87413 13.1534 5.68255C13.5809 7.30682 14 9.38039 14 11.2466H15C15 9.2533 14.556 7.08286 14.1205 5.42802C13.9017 4.59688 13.683 3.88811 13.5188 3.38653C13.4366 3.13563 13.368 2.93627 13.3197 2.79903C13.2956 2.73041 13.2765 2.67729 13.2633 2.641C13.2567 2.62285 13.2516 2.60891 13.2481 2.59934C13.2463 2.59456 13.245 2.59087 13.244 2.58829C13.2435 2.587 13.2432 2.58598 13.2429 2.58525C13.2428 2.58489 13.2426 2.58459 13.2426 2.58437C13.2425 2.58426 13.2425 2.58414 13.2425 2.58409C13.2424 2.58399 13.2424 2.58391 12.7739 2.75862ZM14.5 11.2466C14.0064 11.1668 14.0065 11.1665 14.0065 11.1662C14.0065 11.1661 14.0066 11.1659 14.0066 11.1657C14.0066 11.1654 14.0067 11.1651 14.0067 11.1649C14.0068 11.1644 14.0069 11.164 14.0069 11.1637C14.007 11.1632 14.007 11.1632 14.0069 11.1636C14.0068 11.1645 14.0063 11.1673 14.0053 11.1719C14.0035 11.1811 14 11.1973 13.9945 11.2195C13.9834 11.2641 13.9643 11.3323 13.9338 11.4163C13.8724 11.5854 13.7674 11.8121 13.5948 12.0399C13.2622 12.4789 12.6498 12.9633 11.4842 13.0003L11.5158 13.9997C12.9992 13.9528 13.8868 13.3105 14.3919 12.6438C14.6382 12.3187 14.7865 11.9979 14.8738 11.7575C14.9176 11.6369 14.9465 11.5349 14.965 11.4605C14.9743 11.4233 14.9809 11.3928 14.9855 11.3701C14.9878 11.3588 14.9896 11.3494 14.9909 11.3421C14.9915 11.3384 14.9921 11.3353 14.9925 11.3327C14.9928 11.3314 14.993 11.3302 14.9931 11.3292C14.9932 11.3287 14.9933 11.3282 14.9934 11.3277C14.9934 11.3275 14.9935 11.3272 14.9935 11.3271C14.9935 11.3268 14.9936 11.3265 14.5 11.2466ZM5.25852 6.97095C4.25732 6.97095 3.53601 7.83791 3.53601 8.80137H4.53601C4.53601 8.30258 4.89333 7.97095 5.25852 7.97095V6.97095ZM3.53601 8.80137C3.53601 9.76821 4.2723 10.6319 5.25852 10.6319V9.63188C4.90227 9.63188 4.53601 9.29696 4.53601 8.80137H3.53601ZM5.25852 10.6319C6.2598 10.6319 6.98111 9.76492 6.98111 8.80137H5.98111C5.98111 9.30025 5.62379 9.63188 5.25852 9.63188V10.6319ZM6.98104 8.80961C6.99715 7.83178 6.25264 6.97095 5.25852 6.97095V7.97095C5.63078 7.97095 5.98916 8.30871 5.98117 8.79314L6.98104 8.80961ZM9.63357 6.97095C8.63235 6.97095 7.9109 7.83784 7.9109 8.80137H8.9109C8.9109 8.30265 9.26823 7.97095 9.63357 7.97095V6.97095ZM7.9109 8.80137C7.9109 9.7683 8.64743 10.6319 9.63357 10.6319V9.63188C9.27724 9.63188 8.9109 9.29687 8.9109 8.80137H7.9109ZM9.63357 10.6319C10.6348 10.6319 11.3561 9.7649 11.3561 8.80137H10.3561C10.3561 9.30027 9.99874 9.63188 9.63357 9.63188V10.6319ZM11.3561 8.80137C11.3561 7.83791 10.6348 6.97095 9.63357 6.97095V7.97095C9.99876 7.97095 10.3561 8.30258 10.3561 8.80137H11.3561ZM3.7394 4.43894C5.18247 3.65193 6.35769 3.28473 7.50235 3.28416C8.64671 3.28359 9.82016 3.64946 11.2597 4.43844L11.7403 3.56152C10.2176 2.72691 8.87495 2.28348 7.50185 2.28416C6.12905 2.28484 4.78541 2.72943 3.2606 3.56101L3.7394 4.43894Z"
      fill="currentColor"
    />
  </svg>
);

const socialLinks = [
  {
    name: "Docs",
    url: "https://zaneops.dev",
    icon: <BookOpen size={15} />
  },
  {
    name: "Support",
    url: "https://zaneops.dev/discord",
    icon: <Discord />
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

  const { setTheme, theme } = useTheme();

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

        <div className="flex gap-4">
          <ToggleGroup
            variant="outline"
            type="single"
            value={theme}
            onValueChange={(value) => value && setTheme(value as Theme)}
            className="gap-0 relative top-0.5 rounded-full border border-border p-0.5"
          >
            <ToggleGroupItem
              className={cn(
                "rounded-full border-none text-grey cursor-pointer",
                "hover:text-card-foreground hover:bg-transparent",
                "data-[state=on]:text-card-foreground shadow-none"
              )}
              value="LIGHT"
            >
              <span className="sr-only">light theme</span>
              <SunIcon size={16} />
            </ToggleGroupItem>
            <ToggleGroupItem
              className={cn(
                "rounded-full border-none text-grey cursor-pointer",
                "hover:text-card-foreground hover:bg-transparent",
                "data-[state=on]:text-card-foreground shadow-none"
              )}
              value="SYSTEM"
            >
              <span className="sr-only">system theme</span>
              <LaptopMinimalIcon size={16} />
            </ToggleGroupItem>
            <ToggleGroupItem
              className={cn(
                "rounded-full border-none text-grey cursor-pointer",
                "hover:text-card-foreground hover:bg-transparent",
                "data-[state=on]:text-card-foreground shadow-none"
              )}
              value="DARK"
            >
              <span className="sr-only">dark theme</span>
              <MoonIcon size={16} />
            </ToggleGroupItem>
          </ToggleGroup>

          {data?.commit_sha && (
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
          {data?.image_version && image_version_url && (
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
          className={cn(
            "absolute -top-1 left-0 w-full shadow-lg  rounded-md max-h-[328px]",
            {
              hidden: hideResultList
            }
          )}
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
                  const targetUrl =
                    resource.type === "project"
                      ? href("/project/:projectSlug/:envSlug", {
                          projectSlug: resource.slug,
                          envSlug: "production"
                        })
                      : resource.type === "environment"
                        ? href("/project/:projectSlug/:envSlug", {
                            projectSlug: resource.project_slug,
                            envSlug: resource.name
                          })
                        : href(
                            "/project/:projectSlug/:envSlug/services/:serviceSlug",
                            {
                              projectSlug: resource.project_slug,
                              envSlug: resource.environment,
                              serviceSlug: resource.slug
                            }
                          );
                  navigate(targetUrl);
                  setOpen(false);
                }}
                key={resource.id}
                className="block"
              >
                <div className="flex items-center gap-1 mb-1">
                  {resource.type === "project" && (
                    <FolderIcon size={15} className="flex-none" />
                  )}
                  {resource.type === "service" &&
                    (resource.kind === "DOCKER_REGISTRY" ? (
                      <ContainerIcon size={15} className="flex-none" />
                    ) : resource.git_provider === "gitlab" ? (
                      <GitlabIcon size={15} className="flex-none" />
                    ) : (
                      <GithubIcon size={15} className="flex-none" />
                    ))}
                  {resource.type === "environment" && (
                    <NetworkIcon size={15} className="flex-none" />
                  )}
                  <p>
                    {resource.type === "environment"
                      ? resource.name
                      : resource.slug}
                  </p>
                </div>
                <div className="text-link text-xs">
                  {resource.type === "project" ? (
                    "projects"
                  ) : resource.type === "service" ? (
                    <div className="flex gap-0.5 items-center">
                      <span className="flex-none">projects</span>
                      <ChevronRight size={13} />
                      <span>{resource.project_slug}</span>
                      <ChevronRight className="flex-none" size={13} />
                      <div
                        className={cn(
                          "rounded-md text-link inline-flex gap-1 items-center",
                          resource.environment === "production" &&
                            "px-1.5 border-none bg-primary text-black",
                          resource.environment.startsWith("preview") &&
                            "px-2 border-none bg-secondary text-black"
                        )}
                      >
                        <span>{resource.environment}</span>
                      </div>
                      <ChevronRight className="flex-none" size={13} />
                      <span className="flex-none">services</span>
                    </div>
                  ) : (
                    <div className="flex gap-0.5 items-center">
                      <span className="flex-none">projects</span>
                      <ChevronRight size={13} />
                      <span>{resource.project_slug}</span>
                      <ChevronRight className="flex-none" size={13} />
                      <div
                        className={cn(
                          "rounded-md text-link inline-flex gap-1 items-center"
                        )}
                      >
                        <span>environments</span>
                      </div>
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
