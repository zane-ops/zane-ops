import type { ComposeStack } from "~/api/types";
import { StatusBadge } from "~/components/status-badge";
import { Card } from "~/components/ui/card";
import { pluralize } from "~/utils";

export type ComposeStackCardProps = Pick<
  ComposeStack,
  "slug" | "id" | "service_statuses" | "urls"
>;

export function ComposeStackCard({
  id,
  slug,
  service_statuses,
  urls
}: ComposeStackCardProps) {
  const total_services = Object.values(service_statuses).filter(
    (service) => service.status !== "SLEEPING"
  ).length;
  const healthy_services = Object.values(service_statuses).filter(
    (status) => status.status == "HEALTHY" || status.status == "COMPLETE"
  ).length;

  return (
    <Card className="rounded-2xl flex group flex-col h-[220px] bg-toggle relative ring-1 ring-transparent hover:ring-primary focus-within:ring-primary transition-colors duration-300">
      {/* TODO */}

      <StatusBadge
        color={
          healthy_services === total_services
            ? "green"
            : healthy_services === 0
              ? "red"
              : "yellow"
        }
      >
        <p>
          {healthy_services}/
          {`${total_services} ${pluralize("Service", total_services)} healthy`}
        </p>
      </StatusBadge>
    </Card>
  );
}
