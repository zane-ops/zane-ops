import type { Route } from "./+types/compose-stack-deployment-details";

export default function ComposeStackDeploymentDetailsPage({
  matches: {
    2: {
      loaderData: { deployment }
    }
  }
}: Route.ComponentProps) {
  return <>compose-stack-deployment-details Page</>;
}
