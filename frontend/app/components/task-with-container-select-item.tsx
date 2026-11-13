import { useQuery } from "@tanstack/react-query";
import { ServerIcon } from "lucide-react";
import type { ComposeStackTask } from "~/api/types";
import { SelectItem } from "~/components/ui/select";
import { swarmQueries } from "~/lib/queries";
import { cn, stringToColor } from "~/lib/utils";
import { TASK_STATUS_COLOR_MAP } from "~/routes/compose/components/compose-stack-service-replica-card";

export type TaskWithContainerSelectItemProps = Pick<
  ComposeStackTask,
  "status"
> & {
  container_id: string;
  node_id?: string | null;
};

export function TaskWithContainerSelectItem({
  container_id,
  node_id,
  status
}: TaskWithContainerSelectItemProps) {
  const color = TASK_STATUS_COLOR_MAP[status];
  const containerColor = stringToColor(container_id);

  const { data: servers = [] } = useQuery(swarmQueries.nodeList());
  const server = servers.find((node) => node_id === node.swarm_node_id);

  let newStatus: string = status;
  if (status === "remove") {
    newStatus = "removed";
  }

  return (
    <SelectItem value={container_id}>
      <div
        className="inline-flex items-center gap-1"
        style={
          {
            "--container-color-light": containerColor.light,
            "--container-color-dark": containerColor.dark
          } as React.CSSProperties
        }
      >
        <span
          data-label
          className="text-[var(--container-color-light)] dark:text-[var(--container-color-dark)] order-last"
        >
          {container_id.substring(0, 12)}{" "}
          {server && (
            <span
              data-server
              className="text-card-foreground inline-flex gap-0.5 items-center"
            >
              <span>on</span>
              <span className="text-grey">{server.hostname}</span>
              <ServerIcon className="size-3 flex-none text-grey relative top-0.5" />
            </span>
          )}
        </span>
        <div
          className={cn(
            "rounded-md bg-link/20 text-link px-1  inline-flex gap-1 items-center py-0",
            {
              "bg-emerald-400/30 dark:bg-emerald-600/20 text-green-600  dark:text-emerald-400":
                color === "green",
              "bg-red-600/25 text-red-700 dark:text-red-400": color === "red",
              "bg-yellow-400/30 dark:bg-yellow-600/20 text-amber-700 dark:text-yellow-300":
                color === "yellow",
              "bg-gray-600/20 dark:bg-gray-600/60 text-card-foreground":
                color === "gray",
              "bg-link/30 text-link": color === "blue"
            }
          )}
        >
          <code className="text-sm">{newStatus}</code>
        </div>
      </div>
    </SelectItem>
  );
}
