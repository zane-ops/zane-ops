import { faker } from "@faker-js/faker";
import { InfoIcon, LoaderIcon } from "lucide-react";
import * as React from "react";
import { SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetCheckbox,
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
  const [isNavigating, setisNavigating] = React.useState(false);

  const currentUrl = new URL(window.location.href);
  const appOrigin = `${currentUrl.protocol}//${settings!.app_domain}`;
  const webhook_site_token = import.meta.env.VITE_WEBHOOK_SITE_TOKEN;
  const webhookOrigin = webhook_site_token
    ? `https://${webhook_site_token}.webhook.site`
    : appOrigin;

  const [webhookURI, setWebhookURI] = React.useState(
    () => stripSlashIfExists(webhookOrigin) + "/api/connectors/github/webhook"
  );

  const [redirectURI, setRedirectURI] = React.useState(
    () => `${appOrigin}/api/connectors/github/setup`
  );

  const [installIntoOrg, setInstallIntoOrg] = React.useState(false);

  const manifest = {
    redirect_url: redirectURI,
    name: `ZaneOps-${faker.lorem.slug(2)}`,
    url: appOrigin,
    hook_attributes: {
      url: webhookURI
    },
    callback_urls: [redirectURI],
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
        installIntoOrg && orgName.trim()
          ? `https://github.com/organizations/${orgName}/settings/apps/new?state=create`
          : `https://github.com/settings/apps/new?state=create`
      }
      method="post"
      className="flex flex-col gap-4 items-start"
      onSubmit={() => {
        setisNavigating(true);
      }}
    >
      <FieldSet required className="w-4/5 flex flex-col gap-1">
        <FieldSetLabel className="flex items-center gap-0.5">
          Webhook URL
        </FieldSetLabel>
        <FieldSetInput
          defaultValue={webhookURI}
          onChange={(ev) => setWebhookURI(ev.currentTarget.value)}
          placeholder="ex: https://admin.zaneops.dev/api/connectors/github/setup"
        />
      </FieldSet>
      <FieldSet required className="w-4/5 flex flex-col gap-1">
        <FieldSetLabel className="flex items-center gap-0.5">
          Redirect URI
        </FieldSetLabel>
        <FieldSetInput
          defaultValue={redirectURI}
          onChange={(ev) => setRedirectURI(ev.currentTarget.value)}
          placeholder="ex: https://admin.zaneops.dev/api/connectors/github/webhook"
        />
      </FieldSet>

      <FieldSet
        name="auto_deploy_enabled"
        className="flex-1 inline-flex gap-2 flex-col"
      >
        <div className="inline-flex gap-2 items-center">
          <FieldSetCheckbox
            checked={installIntoOrg}
            onCheckedChange={(checked) => setInstallIntoOrg(Boolean(checked))}
          />

          <FieldSetLabel className="inline-flex gap-1 items-center">
            <span>Install into organization ?</span>
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger>
                  <InfoIcon size={15} />
                </TooltipTrigger>
                <TooltipContent className="max-w-48">
                  Check this if you are installing your GitHub app in an
                  organization.
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </FieldSetLabel>
        </div>
      </FieldSet>

      {installIntoOrg && (
        <FieldSet required className="w-4/5 flex flex-col gap-1">
          <FieldSetLabel className="flex items-center gap-0.5">
            Organization name
          </FieldSetLabel>
          <FieldSetInput
            required
            onChange={(ev) => setOrgName(ev.currentTarget.value)}
            placeholder="ex: zane-ops"
          />
        </FieldSet>
      )}

      <input
        type="hidden"
        name="manifest"
        value={JSON.stringify(manifest)}
        readOnly
      />
      <SubmitButton isPending={isNavigating}>
        {isNavigating ? (
          <>
            <LoaderIcon className="animate-spin" size={15} />
            <span>Going to to github...</span>
          </>
        ) : (
          "Create Github app"
        )}
      </SubmitButton>
    </form>
  );
}
