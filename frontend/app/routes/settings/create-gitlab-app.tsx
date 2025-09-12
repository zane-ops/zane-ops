import { AlertCircleIcon, ExternalLinkIcon, LoaderIcon } from "lucide-react";
import * as React from "react";
import { Link, redirect, useFetcher } from "react-router";

import { type RequestInput, apiClient } from "~/api/client";
import { Code } from "~/components/code";
import { SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetHidableInput,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
import { Separator } from "~/components/ui/separator";

import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { serverQueries } from "~/lib/queries";
import { getFormErrorsFromResponseData } from "~/lib/utils";
import { queryClient } from "~/root";
import { getCsrfTokenHeader, metaTitle } from "~/utils";
import type { Route } from "./+types/create-gitlab-app";

export function meta() {
  return [metaTitle("New Gitlab app")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader() {
  const settings = await queryClient.ensureQueryData(serverQueries.settings);

  return { settings };
}

export default function CreateGitlabAppPage({
  loaderData: { settings }
}: Route.ComponentProps) {
  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">New Gitlab app</h2>
      </div>
      <Separator />

      <CreateGitlabAppForm settings={settings} />
    </section>
  );
}

type CreateGitlabAppFormProps = {
  settings: Route.ComponentProps["loaderData"]["settings"];
};

function CreateGitlabAppForm({ settings }: CreateGitlabAppFormProps) {
  const [gitlabURL, setGitlabURL] = React.useState("https://gitlab.com");

  const [isSecretShown, setIsSecretShown] = React.useState(false);

  const fetcher = useFetcher<typeof clientAction>();

  const currentUrl = new URL(window.location.href);
  const appOrigin = `${currentUrl.protocol}//${settings!.app_domain}`;
  const webhook_site_token = import.meta.env.VITE_WEBHOOK_SITE_TOKEN;
  const callbackOrigin = webhook_site_token
    ? `https://${webhook_site_token}.webhook.site`
    : appOrigin;

  const redirectURI = `${callbackOrigin}/api/connectors/gitlab/setup`;

  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  return (
    <>
      <p>
        To connect ZaneOps to your Gitlab account, you need to&nbsp;
        <Link
          to={`${gitlabURL}/-/profile/applications`}
          target="_blank"
          className="inline-flex gap-0.5 text-link break-words whitespace-break-spaces"
        >
          <span className="break-words whitespace-break-spaces">
            create a new gitlab application
          </span>
          <ExternalLinkIcon size={15} className="flex-none relative top-0.5" />
        </Link>
        &nbsp; on your account with the following details:
      </p>
      <ul className="list-disc list-inside ml-4">
        <li>
          <span className="text-grey select-none">Name:</span> ZaneOps
        </li>
        <li>
          <span className="text-grey select-none">Redirect URI:</span>&nbsp;
          <span className="text-link">{redirectURI}</span>
        </li>
        <li>
          <span className="text-grey select-none">Scopes:</span> api, read_user,
          read_repository
        </li>
      </ul>

      <p>
        Once created, please copy the <Code>Application ID</Code> and&nbsp;
        <Code>Application Secret</Code> in the fields below
      </p>

      {errors.non_field_errors && (
        <Alert variant="destructive" className="my-2">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{errors.non_field_errors}</AlertDescription>
        </Alert>
      )}
      <fetcher.Form method="post" className="flex flex-col gap-4 items-start">
        <FieldSet
          className="w-full md:w-4/5 flex flex-col gap-1"
          required
          name="name"
          errors={errors.name}
        >
          <FieldSetLabel className="flex items-center gap-0.5">
            Name
          </FieldSetLabel>
          <FieldSetInput autoFocus placeholder="ex: zn-gitlab" />
        </FieldSet>
        <FieldSet
          className="w-full md:w-4/5 flex flex-col gap-1"
          required
          name="app_id"
          errors={errors.app_id}
        >
          <FieldSetLabel className="flex items-center gap-0.5">
            Application ID
          </FieldSetLabel>
          <FieldSetInput />
        </FieldSet>

        <FieldSet
          className="w-full md:w-4/5 flex flex-col gap-1"
          required
          name="app_secret"
          errors={errors.app_secret}
        >
          <FieldSetLabel className="flex items-center gap-0.5">
            Application Secret
          </FieldSetLabel>
          <FieldSetHidableInput label="secret" />
        </FieldSet>

        <FieldSet
          className="w-full md:w-4/5 flex flex-col gap-1"
          name="gitlab_url"
          required
          errors={errors.gitlab_url}
        >
          <FieldSetLabel className="flex items-center gap-0.5">
            Gitlab URL
          </FieldSetLabel>
          <FieldSetInput
            defaultValue={gitlabURL}
            onChange={(e) => setGitlabURL(e.currentTarget.value)}
            placeholder="ex: https://example.gitlab.com"
          />
        </FieldSet>

        <FieldSet
          className="w-full md:w-4/5 flex flex-col gap-1"
          name="redirect_uri"
          errors={errors.redirect_uri}
        >
          <FieldSetLabel className="flex items-center gap-0.5">
            Redirect URI
          </FieldSetLabel>
          <FieldSetInput defaultValue={redirectURI} />
        </FieldSet>

        <SubmitButton isPending={fetcher.state !== "idle"}>
          {fetcher.state !== "idle" ? (
            <>
              <LoaderIcon className="animate-spin" size={15} />
              <span>Creating gitlab app...</span>
            </>
          ) : (
            "Create Gitlab app"
          )}
        </SubmitButton>
      </fetcher.Form>
    </>
  );
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const formData = await request.formData();

  const userData = {
    app_id: formData.get("app_id")?.toString() ?? "",
    app_secret: formData.get("app_secret")?.toString() ?? "",
    name: formData.get("name")?.toString() ?? "",
    redirect_uri: formData.get("redirect_uri")?.toString() ?? "",
    gitlab_url: formData.get("gitlab_url")?.toString() ?? ""
  } satisfies RequestInput<"post", "/api/connectors/gitlab/create/">;

  const { data, error } = await apiClient.POST(
    "/api/connectors/gitlab/create/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      body: userData
    }
  );

  if (error) {
    return {
      errors: error
    };
  }

  const { state } = data;

  const redirectURL = new URL(`${userData.gitlab_url}/oauth/authorize`);

  redirectURL.searchParams.set("client_id", userData.app_id);
  redirectURL.searchParams.set("redirect_uri", userData.redirect_uri);
  redirectURL.searchParams.set("response_type", "code");
  redirectURL.searchParams.set("state", state);
  redirectURL.searchParams.set("scope", "api read_user read_repository");

  throw redirect(redirectURL.toString());
}
