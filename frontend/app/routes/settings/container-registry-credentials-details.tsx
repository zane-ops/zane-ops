import { Separator } from "~/components/ui/separator";
import type { Route } from "./+types/container-registry-credentials-details";

export default function ContainerRegistryCredentialDetailsPage({}: Route.ComponentProps) {
  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Edit Registry Credentials</h2>
      </div>
      <Separator />
    </section>
  );
}
