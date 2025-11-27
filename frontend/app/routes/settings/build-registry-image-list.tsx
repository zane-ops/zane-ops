import { ExternalLinkIcon } from "lucide-react";
import { Separator } from "~/components/ui/separator";
import { buildRegistryQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { metaTitle } from "~/utils";
import type { Route } from "./+types/build-registry-image-list";

export function meta() {
  return [
    metaTitle("Registry Image List")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const registry = await queryClient.ensureQueryData(
    buildRegistryQueries.single(params.id)
  );
  return {
    registry
  };
}

export default function BuildRegistryImageListPage({
  loaderData: { registry }
}: Route.ComponentProps) {
  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">
          Images included in&nbsp;
          <span>`</span>
          {registry.name}
          <span>`</span>
        </h2>
      </div>
      <Separator />
      <h3 className="text-grey">
        List of docker images pushed to{" "}
        <a
          href={`${registry.is_secure ? "https" : "http"}://${registry.registry_domain}`}
          target="_blank"
          className="underline text-link inline-flex items-center gap-1"
          rel="noreferrer"
        >
          <span>{`${registry.is_secure ? "https" : "http"}://${registry.registry_domain}`}</span>
          <ExternalLinkIcon size={16} className="flex-none" />
        </a>
      </h3>
    </section>
  );
}
