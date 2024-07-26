import { Link, createFileRoute } from "@tanstack/react-router";
import { ArrowRight, Container, Github } from "lucide-react";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import { MetaTitle } from "~/components/meta-title";
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

export const Route = createFileRoute(
  "/_dashboard/project/$slug/create-service"
)({
  component: withAuthRedirect(CreateService)
});

function CreateService() {
  const { slug } = Route.useParams();
  return (
    <main>
      <MetaTitle title="Create Service" />
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
              <Link to={`/project/${slug}`} className="capitalize">
                {slug}
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>

          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>Create service</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <div className="flex h-[60vh] flex-grow justify-center items-center">
        <div className="card  flex lg:w-[30%] md:w-[50%] w-full flex-col gap-6">
          <h1 className="text-3xl font-bold">New Service</h1>
          <div className="flex flex-col gap-3">
            <Button
              asChild
              variant="secondary"
              className="flex gap-3  font-semibold items-center justify-center p-10"
            >
              <Link to="docker">
                <Container /> From Docker Image <ArrowRight />
              </Link>
            </Button>

            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button
                    asChild
                    variant="secondary"
                    className="flex gap-3 items-center  font-semibold  justify-center p-10"
                  >
                    <Link to="#" className="cursor-not-allowed">
                      <Github /> From A Github Repository
                      <ArrowRight />
                    </Link>
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="right" align="center">
                  <div className="capitalize">Coming soon</div>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>
      </div>
    </main>
  );
}
