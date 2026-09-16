import { PlusIcon } from "lucide-react";
import { Link } from "react-router";
import { Button } from "~/components/ui/button";
import { Separator } from "~/components/ui/separator";
import { metaTitle } from "~/lib/utils";
import type { Route } from "./+types/server-list";

export function meta() {
  return [metaTitle("Servers")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({}: Route.ClientLoaderArgs) {
  return;
}

export default function ServerListPage({}: Route.ComponentProps) {
  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Servers</h2>
        <Button asChild variant="secondary" className="flex gap-2">
          <Link to="new" prefetch="intent">
            Add server <PlusIcon size={18} />
          </Link>
        </Button>
      </div>
      <Separator />
      <h3 className="text-grey">
        Add and manage the servers that make up your ZaneOps cluster. Services
        can be deployed to any server in this list.
      </h3>
    </section>
  );
}
