import { ArrowBigUpDash, LoaderIcon, Sparkles } from "lucide-react";
import { Outlet, redirect, useFetcher } from "react-router";
import { serverQueries, userQueries, versionQueries } from "~/lib/queries";
import { cn, notFound } from "~/lib/utils";
import { metaTitle } from "~/utils";

import { useQuery } from "@tanstack/react-query";
import * as React from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast } from "sonner";
import { StatusBadge } from "~/components/status-badge";
import { Button, SubmitButton } from "~/components/ui/button";

import { CommandBarTrigger } from "~/components/commandbar/commandbar-trigger";
import {
  Header,
  UserDropdown,
  WorkspaceMembershipList
} from "~/components/header";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "~/components/ui/dialog";
import { ZANE_UPDATE_TOAST_ID } from "~/lib/constants";
import { queryClient } from "~/root";
import {
  type clientAction,
  pollUntilUpdateDone
} from "~/routes/trigger-update";
import type { Route } from "./+types/dashboard-layout";

export function meta() {
  return [metaTitle("Dashboard")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const memberships = await queryClient.ensureQueryData(
    userQueries.memberships
  );

  if (memberships === null) {
    throw redirect("/login");
  }

  const workspaces = memberships.map((m) => m.workspace.id);
  if (!workspaces.includes(params.workspaceId)) {
    throw notFound("Workspace Not found");
  }
}

export default function DashboardLayout({
  matches: {
    "1": { loaderData }
  }
}: Route.ComponentProps) {
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

  const ongoingUpdateQuery = useQuery(serverQueries.ongoingUpdate);

  React.useEffect(() => {
    // resume polling + loading toast if an update is already ongoing
    // (e.g. the page was reloaded while ZaneOps was updating)
    if (ongoingUpdateQuery.data?.update_ongoing) {
      pollUntilUpdateDone();
    }
  }, [ongoingUpdateQuery.data]);

  React.useEffect(() => {
    if (
      import.meta.env.PROD &&
      latestVersion?.tag &&
      previousVersion &&
      previousVersion !== "canary" && // ignore canary as it is the latest version
      !previousVersion.startsWith("pr-") && // ignore pr branch versions
      previousVersion !== latestVersion.tag &&
      !(ongoingUpdateQuery.data && ongoingUpdateQuery.data.update_ongoing)
    ) {
      toast.success("New version of ZaneOps available !", {
        description: latestVersion.tag,
        closeButton: true,
        duration: Number.POSITIVE_INFINITY,
        id: ZANE_UPDATE_TOAST_ID,
        icon: <Sparkles size={17} />,
        action: (
          <Button
            onClick={() => {
              setshowUpdateDialog(true);
              toast.dismiss(ZANE_UPDATE_TOAST_ID);
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
  }, [previousVersion, latestVersion?.tag, ongoingUpdateQuery]);

  if (!loaderData.user || !loaderData.memberships) return null;

  return (
    <>
      <Header
        leftSlot={
          <WorkspaceMembershipList memberships={loaderData.memberships} />
        }
        rigthSlot={
          <>
            <CommandBarTrigger />
            <UserDropdown user={loaderData.user} />
          </>
        }
      />
      <main
        className={cn(
          "grow container p-6 relative overflow-y-clip",
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
                  <p className="text-start text-lg font-medium text-card-foreground">
                    Release notes:
                  </p>
                  <div className="flex my-2 flex-col gap-2.5 markdown py-2 rounded-lg bg-muted p-4 max-h-[500px] overflow-auto text-card-foreground">
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
    </>
  );
}
