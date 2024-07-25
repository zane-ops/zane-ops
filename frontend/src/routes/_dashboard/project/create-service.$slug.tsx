import { Link, createFileRoute } from "@tanstack/react-router";
import { ArrowRight, Container, Github } from "lucide-react";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import { MetaTitle } from "~/components/meta-title";
import { Button } from "~/components/ui/button";

export const Route = createFileRoute(
  "/_dashboard/project/create-service/$slug"
)({
  component: withAuthRedirect(CreateService)
});

function CreateService() {
  return (
    <main>
      <MetaTitle title="Create Service" />
      <div className="flex h-[60vh] flex-grow justify-center items-center">
        <div className="card  flex lg:w-[30%] md:w-[50%] w-full flex-col gap-6">
          <h1 className="text-3xl font-bold">New Service</h1>
          <div className="flex flex-col gap-3">
            <Button
              asChild
              variant="secondary"
              className="flex gap-3  font-semibold items-center justify-center p-10"
            >
              <Link to="">
                <Container /> From Docker Image <ArrowRight />
              </Link>
            </Button>

            <Button
              asChild
              variant="secondary"
              className="flex gap-3 items-center  font-semibold  justify-center p-10"
            >
              <Link to="/docker">
                <Github /> From A Github Repository
                <ArrowRight />
              </Link>
            </Button>
          </div>
        </div>
      </div>
    </main>
  );
}
