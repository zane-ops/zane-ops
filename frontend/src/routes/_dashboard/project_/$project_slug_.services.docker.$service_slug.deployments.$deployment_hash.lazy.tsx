import { Link, createLazyFileRoute } from "@tanstack/react-router";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import { Loader } from "~/components/loader";
import { MetaTitle } from "~/components/meta-title";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from "~/components/ui/breadcrumb";

export const Route = createLazyFileRoute(
  "/_dashboard/project/$project_slug/services/docker/$service_slug/deployments/$deployment_hash"
)({
  component: withAuthRedirect(DeploymentLayout)
});

const TABS = {
  LOGS: "logs",
  HTTP_LOGS: "http-logs",
  DETAILS: "details"
} as const;

function DeploymentLayout(): JSX.Element {
  const { project_slug, service_slug, deployment_hash } = Route.useParams();

  const isLoading = false;
  const unprefixed_hash = deployment_hash.substring(8);
  return (
    <>
      <Breadcrumb>
        <BreadcrumbList className="text-sm">
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/">Projects</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to={`/project/${project_slug}/`}>{project_slug}</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>

          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link
                to={`/project/${project_slug}/services/docker/${service_slug}`}
              >
                {service_slug}
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>

          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{deployment_hash}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      {isLoading ? (
        <>
          <div className="col-span-full">
            <Loader className="h-[70vh]" />
          </div>
        </>
      ) : (
        <>
          <MetaTitle title={`${service_slug} / ${unprefixed_hash}`} />
          <h1>
            {service_slug} / {deployment_hash}
          </h1>
        </>
      )}
    </>
  );
}
