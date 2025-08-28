import type { Route } from "./+types/review-deployment";

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  // TODO...
}

export default function ReviewEnvDeploymentPage({
  params
}: Route.ComponentProps) {
  return (
    <section className="size-full grow flex flex-col items-center justify-center absolute isnet-0">
      <h1 className="text-2xl font-medium">
        Approve Fork Preview deployment ?
      </h1>
    </section>
  );
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const formData = await request.formData();

  // TODO...
}
