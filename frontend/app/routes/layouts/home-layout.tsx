import { useQuery } from "@tanstack/react-query";
import { Outlet } from "react-router";
import { CommandBar } from "~/components/commandbar/commandbar";
import { MAIN_NAV_GROUPS } from "~/components/commandbar/commandbar-nav-items";
import { CommandBarTrigger } from "~/components/commandbar/commandbar-trigger";
import { Header } from "~/components/header/header";
import { UserHeaderDropdown } from "~/components/header/user-header-dropdown";
import { userQueries } from "~/lib/queries";
import { cn } from "~/lib/utils";
import type { Route } from "./+types/home-layout";

export default function HomeLayoutPage({
  matches: {
    "1": { loaderData }
  }
}: Route.ComponentProps) {
  const { data: user } = useQuery({
    ...userQueries.authedUser,
    initialData: loaderData.user
  });

  if (!user) return null;

  return (
    <>
      <Header
        rigthSlot={[<CommandBarTrigger />, <UserHeaderDropdown user={user} />]}
      />
      <main
        className={cn(
          "grow container p-6 relative overflow-y-clip",
          "flex flex-col gap-10",
          !import.meta.env.PROD ? "my-14" : "my-7"
        )}
      >
        <Outlet />
      </main>
    </>
  );
}
