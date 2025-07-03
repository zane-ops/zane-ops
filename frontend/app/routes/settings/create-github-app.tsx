import { faker } from "@faker-js/faker";
import { useQuery } from "@tanstack/react-query";
import { InfoIcon } from "lucide-react";
import * as React from "react";
import { Button } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
import { Separator } from "~/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { serverQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { metaTitle, stripSlashIfExists } from "~/utils";
import type { Route } from "./+types/create-github-app";

export function meta() {
  return [metaTitle("New GitHub app")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader() {
  const settings = await queryClient.ensureQueryData(serverQueries.settings);

  return { settings };
}

export default function CreateGithubAppPage({
  loaderData: { settings }
}: Route.ComponentProps) {
  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">New GitHub app</h2>
      </div>
      <Separator />
      <h3>
        To connect ZaneOps to your GitHub account, you will need to create and
        install a GitHub app.
      </h3>
      <CreateGithubAppForm settings={settings} />
    </section>
  );
}

function CreateGithubAppForm({ settings }: Route.ComponentProps["loaderData"]) {
  const [orgName, setOrgName] = React.useState("");

  const currentUrl = new URL(window.location.href);
  const appOrigin = `${currentUrl.protocol}//${settings!.app_domain}`;
  const webhook_site_token = import.meta.env.VITE_WEBHOOK_SITE_TOKEN;
  const webhookOrigin = webhook_site_token
    ? `https://${webhook_site_token}.webhook.site`
    : appOrigin;

  const manifest = {
    redirect_url: `${appOrigin}/api/connectors/github/setup`,
    name: `ZaneOps-${faker.lorem.slug(2)}`,
    url: appOrigin,
    hook_attributes: {
      url: stripSlashIfExists(webhookOrigin) + "/api/connectors/github/webhook"
    },
    callback_urls: [`${appOrigin}/api/connectors/github/setup`],
    public: false,
    request_oauth_on_install: true,
    default_permissions: {
      contents: "read",
      metadata: "read",
      emails: "read",
      pull_requests: "write"
    },
    default_events: ["pull_request", "push"]
  };

  return (
    <form
      action={
        orgName.trim()
          ? `https://github.com/organizations/${orgName}/settings/apps/new?state=create`
          : `https://github.com/settings/apps/new?state=create`
      }
      method="post"
      className="flex flex-col gap-4 items-start"
    >
      <FieldSet className="w-4/5 flex flex-col gap-1">
        <FieldSetLabel className="flex items-center gap-0.5">
          Organization name
          <TooltipProvider>
            <Tooltip delayDuration={0}>
              <TooltipTrigger>
                <InfoIcon size={15} className="text-grey" />
              </TooltipTrigger>
              <TooltipContent className="max-w-64 dark:bg-card">
                Fill this input if you are installing your GitHub app in an
                organization.
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </FieldSetLabel>
        <FieldSetInput
          onChange={(ev) => setOrgName(ev.currentTarget.value)}
          autoFocus
          placeholder="ex: zane-ops"
        />
      </FieldSet>
      <input
        type="hidden"
        name="manifest"
        value={JSON.stringify(manifest)}
        readOnly
      />
      <Button type="submit">Create GitHub app</Button>
    </form>
  );
}
