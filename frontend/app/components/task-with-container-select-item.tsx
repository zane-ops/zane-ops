import type { ComposeStackTask } from "~/api/types";
import { SelectItem } from "~/components/ui/select";
import { cn } from "~/lib/utils";
import { TASK_STATUS_COLOR_MAP } from "~/routes/compose/components/compose-stack-service-replica-card";
import { stringToColor } from "~/utils";

export type TaskWithContainerSelectItemProps = Pick<
  ComposeStackTask,
  "status"
> & {
  container_id: string;
};

export function TaskWithContainerSelectItem({
  container_id,
  status
}: TaskWithContainerSelectItemProps) {
  const color = TASK_STATUS_COLOR_MAP[status];
  const containerColor = stringToColor(container_id);

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
          className="text-[var(--container-color-light)] dark:text-[var(--container-color-dark)]"
        >
          {container_id.substring(0, 12)}
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
