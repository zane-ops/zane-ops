import { Link, Outlet, createFileRoute } from "@tanstack/react-router";
import {
  Container,
  KeyRound,
  Rocket,
  Settings,
  TriangleAlert
} from "lucide-react";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import { MetaTitle } from "~/components/meta-title";
import { StatusBadge } from "~/components/status-badge";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from "~/components/ui/breadcrumb";
import { Button } from "~/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "~/components/ui/tabs";

export const Route = createFileRoute(
  "/_dashboard/project/$project_slug/services/docker/$service_slug"
)({
  component: withAuthRedirect(ServiceDetails)
});

function ServiceDetails() {
  const { project_slug, service_slug } = Route.useParams();
  const baseUrl = `/project/${project_slug}/services/docker/${service_slug}`;

  return (
    <>
      <MetaTitle title={`${service_slug}`} />
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
            <BreadcrumbPage>{service_slug}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <div className="flex items-center justify-between">
        <div className="mt-10">
          <h1 className="text-2xl">nginxdemo</h1>
          <p className="flex gap-1 items-center">
            <Container size={15} />{" "}
            <span className="text-gray-500 dark:text-gray-400 text-sm">
              nginxdemo/hello:latest
            </span>
          </p>
          <div className="flex gap-3 items-center">
            <a
              href="https://nginxdemo.zaneops.local"
              target="_blank"
              className="underline text-link text-sm"
            >
              nginxdemo.zaneops.local
            </a>
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <span>
                    <StatusBadge
                      className="relative top-0.5 text-xs"
                      color="gray"
                      isPing={false}
                    >
                      <span>+2 urls</span>
                    </StatusBadge>
                  </span>
                </TooltipTrigger>
                <TooltipContent align="end" side="right" className="px-4 py-3">
                  <ul>
                    <li>
                      <a
                        href="https://nginxdemo.zaneops.local"
                        target="_blank"
                        className="underline text-link text-sm"
                      >
                        nginx-demo.zaneops.local
                      </a>
                    </li>
                    <li>
                      <a
                        href="https://nginxdemo.zaneops.local"
                        target="_blank"
                        className="underline text-link text-sm"
                      >
                        nginx-demo-docker.zaneops.local
                      </a>
                    </li>
                  </ul>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="warning">
            <TriangleAlert size={15} />
            <span className="mx-1">1 unapplied change</span>
          </Button>

          <Button variant="secondary">deploy</Button>
        </div>
      </div>
      <Tabs defaultValue="deployment" className="w-full mt-5">
        <TabsList className="w-full items-start justify-start bg-background rounded-none border-b border-border">
          <TabsTrigger value="deployment" asChild>
            <Link className="flex gap-2 items-center" to={baseUrl}>
              Deployments <Rocket size={15} />
            </Link>
          </TabsTrigger>

          <TabsTrigger value="envVariable">
            <Link
              className="flex gap-2 items-center"
              to={`${baseUrl}/env-variables`}
            >
              Env Variables <KeyRound size={15} />
            </Link>
          </TabsTrigger>

          <TabsTrigger value="settings">
            <Link
              className="flex gap-2 items-center"
              to={`${baseUrl}/settings`}
            >
              Settings <Settings size={15} />
            </Link>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="deployment">
          <Outlet />
        </TabsContent>

        <TabsContent value="envVariable">
          <Outlet />
        </TabsContent>
        <TabsContent value="settings">
          <Outlet />
        </TabsContent>
      </Tabs>
    </>
  );
}
