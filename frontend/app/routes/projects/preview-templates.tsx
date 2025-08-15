import { ExternalLinkIcon, PlusIcon } from "lucide-react";
import { Link } from "react-router";
import { Button } from "~/components/ui/button";
import { Separator } from "~/components/ui/separator";
import type { Route } from "./+types/preview-templates";

export default function PreviewTemplatesPage({}: Route.ComponentProps) {
  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Preview templates</h2>
        <Button asChild variant="secondary" className="flex gap-2">
          <Link to="new" prefetch="intent">
            New Template <PlusIcon size={18} />
          </Link>
        </Button>
      </div>
      <Separator />
      <p className="text-grey">
        See all the templates for Preview environments,{" "}
        <a
          href="https://zaneops.dev/knowledge-base/preview-templates/"
          target="_blank"
          className="text-link underline inline-flex gap-1 items-center"
        >
          Read the docs <ExternalLinkIcon size={12} />
        </a>
      </p>
    </section>
  );
}
