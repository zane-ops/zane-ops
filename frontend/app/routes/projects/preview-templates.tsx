import { useQuery } from "@tanstack/react-query";
import {
  BookTemplateIcon,
  ChevronRightIcon,
  ContainerIcon,
  ExternalLinkIcon,
  GitForkIcon,
  KeyRoundIcon,
  LockIcon,
  PlusIcon
} from "lucide-react";
import { Link } from "react-router";
import { Code } from "~/components/code";
import { StatusBadge } from "~/components/status-badge";
import { Button } from "~/components/ui/button";
import { Card, CardContent } from "~/components/ui/card";
import { Separator } from "~/components/ui/separator";
import { type PreviewTemplate, previewTemplatesQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import type { Route } from "./+types/preview-templates";

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const templates = await queryClient.ensureQueryData(
    previewTemplatesQueries.list(params.projectSlug)
  );

  return {
    templates
  };
}

export default function PreviewTemplatesPage({
  loaderData,
  params
}: Route.ComponentProps) {
  const { data: templates } = useQuery({
    ...previewTemplatesQueries.list(params.projectSlug),
    initialData: loaderData.templates
  });

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
        Preview templates define the configuration of preview environments.
        These environments are created when triggered by either an API call or a
        pull request. &nbsp;
        <a
          href="https://zaneops.dev/knowledge-base/preview-templates/"
          target="_blank"
          className="text-link underline inline-flex gap-1 items-center"
        >
          Learn more <ExternalLinkIcon size={12} />
        </a>
      </p>

      <ul className="flex flex-col gap-2">
        {templates.map((template) => (
          <PreviewTemplateCard key={template.id} template={template} />
        ))}
      </ul>
    </section>
  );
}

type PreviewTemplateCardProps = {
  template: PreviewTemplate;
};

function PreviewTemplateCard({ template }: PreviewTemplateCardProps) {
  return (
    <Card>
      <CardContent className="relative rounded-md p-4 gap-4 flex flex-col items-start md:flex-row bg-toggle">
        <BookTemplateIcon
          size={24}
          className="flex-none text-grey relative top-1.5"
        />

        <div className="flex flex-col flex-1 gap-3">
          <h4 className="flex items-center gap-2">
            <Link
              className="text-lg font-medium after:absolute after:inset-0"
              to={`./${template.slug}`}
            >
              {template.slug}
            </Link>
            {template.is_default && (
              <StatusBadge color="blue" pingState="hidden">
                default
              </StatusBadge>
            )}
          </h4>

          <dl className="flex flex-col gap-1.5 items-start text-sm">
            <div className="flex items-center gap-1">
              <dt className="text-grey inline-flex items-center gap-1.5">
                <GitForkIcon size={15} className="text-grey flex-none" />
                <span>Base environment:</span>
              </dt>
              <dd>{template.base_environment.name}</dd>
            </div>

            <div className="flex items-center gap-1">
              <dt className="text-grey inline-flex items-center gap-1.5">
                <ContainerIcon size={15} className="text-grey flex-none" />
                <span>Services to clone:</span>
              </dt>
              <dd className="flex items-center gap-0.5 flex-wrap">
                {template.clone_strategy === "ALL" ? (
                  <span className="font-mono">{`[all services]`}</span>
                ) : (
                  template.services_to_clone.map((v) => (
                    <Code key={v.id}>{v.slug}</Code>
                  ))
                )}
              </dd>
            </div>

            <div className="flex items-center gap-1">
              <dt className="text-grey inline-flex items-center gap-1.5">
                <KeyRoundIcon size={15} className="text-grey flex-none" />
                <span>Default variables:</span>
              </dt>
              <dd className="flex items-center gap-0.5 flex-wrap">
                {template.variables.length === 0 ? (
                  <span className="font-mono">{`[no variable]`}</span>
                ) : (
                  template.variables.map((v) => <Code key={v.id}>{v.key}</Code>)
                )}
              </dd>
            </div>

            <div className="flex items-center gap-1">
              <dt className="text-grey inline-flex items-center gap-1.5">
                <LockIcon size={15} className="text-grey flex-none" />
                <span>With auth:</span>
              </dt>
              <dd>{template.auth_enabled ? "yes" : "no"}</dd>
            </div>
          </dl>
        </div>

        <ChevronRightIcon
          size={20}
          className="flex-none text-grey self-center"
        />
      </CardContent>
    </Card>
  );
}
