import { ExternalLinkIcon } from "lucide-react";
import type { Route } from "./+types/project-environment-list";

export default function EnvironmentListPage({
  matches: {
    "2": {
      data: { project }
    }
  }
}: Route.ComponentProps) {
  const environments = project.environments;
  return (
    <section className="my-6 gap-2">
      <h2 className="text-lg">List of environments</h2>
      <p className="text-grey">
        Each environment gives you an isolated instance of each service.&nbsp;
        <a
          href="#"
          className="underline text-link inline-flex gap-1 items-center"
        >
          Read the docs <ExternalLinkIcon size={12} />
        </a>
      </p>

      <ul className="grid gap-4">
        {environments.map((env) => (
          <li key={env.id}>{env.name}</li>
        ))}
      </ul>
    </section>
  );
}
