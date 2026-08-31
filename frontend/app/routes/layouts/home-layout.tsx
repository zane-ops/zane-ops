import { useQuery } from "@tanstack/react-query";
import { HouseHeartIcon } from "lucide-react";
import { Link, Outlet, href } from "react-router";
import { CommandBarTrigger } from "~/components/commandbar/commandbar-trigger";
import { Header } from "~/components/header/header";
import { UserHeaderDropdown } from "~/components/header/user-header-dropdown";
import { Button } from "~/components/ui/button";
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
        leftSlot={
          <Button
            variant="ghost"
            asChild
            className="inline-flex gap-1.5 py-1 px-2 rounded-sm text-sm h-8"
          >
            <Link to={href("/")}>
              <HouseHeartIcon className="size-4 flex-none text-grey" />
              <span className="whitespace-nowrap">Home</span>
            </Link>
          </Button>
        }
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
