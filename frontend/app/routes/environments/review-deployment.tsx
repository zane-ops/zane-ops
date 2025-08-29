import { useQuery } from "@tanstack/react-query";
import { ExternalLinkIcon, LockKeyholeIcon, SirenIcon } from "lucide-react";
import { Form, href, redirect, useNavigation } from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import { GithubLogo } from "~/components/github-logo";
import { ThemedLogo } from "~/components/logo";
import { SubmitButton } from "~/components/ui/button";
import { environmentQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { metaTitle } from "~/utils";
import type { Route } from "./+types/review-deployment";

export function meta() {
  return [metaTitle("Authorize Preview Deployment ")];
}

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const environment = await queryClient.ensureQueryData(
    environmentQueries.pendingReview(params.projectSlug, params.envSlug)
  );

  return {
    environment
  };
}

export default function ReviewEnvDeploymentPage({
  loaderData: { environment }
}: Route.ComponentProps) {
  const preview_meta = environment.preview_metadata!;

  const path = new URL(preview_meta.head_repository_url).pathname
    .substring(1)
    .replace(/\.git$/, "");

  const request_name = preview_meta.git_app?.gitlab
    ? "merge request"
    : "pull request";

  const navigation = useNavigation();

  return (
    <section className="size-full grow flex flex-col gap-6 items-center justify-center md:px-8 pt-30 pb-24">
      <div className="flex items-center gap-4">
        <GithubLogo className="size-9 md:size-18 flex-none" />
        <div className="flex items-center gap-2">
          <hr className="h-px max-w-40 w-10 md:w-20 border-dashed border border-grey" />
          <LockKeyholeIcon className="flex-none size-5 md:size-8" />
          <hr className="h-px max-w-40 w-10 md:w-20 border-dashed border border-grey" />
        </div>
        <ThemedLogo className="size-12 md:size-24 flex-none" />
      </div>
      <h1 className="text-2xl font-medium flex items-center flex-wrap gap-0.5">
        <SirenIcon
          className="hidden md:block text-red-400 relative bottom-0.5"
          size={32}
        />
        <span>Preview Deployment Blocked</span>
        <SirenIcon
          className="hidden md:block text-red-400 relative bottom-0.5"
          size={32}
        />
      </h1>
      <div className="flex flex-col gap-4 text-grey text-pretty md:text-center">
        <p>
          The preview deployment for {request_name}{" "}
          <a
            href={preview_meta.external_url}
            target="_blank"
            className="text-link inline-flex items-center gap-0.5"
          >
            {path}#{preview_meta.pr_number}{" "}
            <ExternalLinkIcon size={15} className="flex-none" />
          </a>{" "}
          has been blocked and is awaiting authorization to be deployed.
        </p>

        <p>
          As a member of this ZaneOps instance, please{" "}
          <a
            href={preview_meta.external_url}
            target="_blank"
            className="text-link inline-flex items-center gap-0.5"
          >
            <span>review the {request_name}</span>
            <ExternalLinkIcon size={15} className="flex-none" />
          </a>{" "}
          and then{" "}
          <strong className="font-semibold">
            approve or decline the deployment
          </strong>
          .
        </p>
      </div>

      <Form
        method="POST"
        className="flex flex-col md:flex-row items-center gap-4 my-6 md:my-10"
      >
        <SubmitButton
          name="decision"
          value="APPROVE"
          isPending={navigation.state !== "idle"}
          variant="default"
        >
          Approve Deployment
        </SubmitButton>
        <SubmitButton
          name="decision"
          value="DECLINE"
          isPending={navigation.state !== "idle"}
          variant="destructive"
        >
          Decline Deployment
        </SubmitButton>
      </Form>
    </section>
  );
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const environment = queryClient.getQueryData(
    environmentQueries.pendingReview(params.projectSlug, params.envSlug)
      .queryKey
  );

  if (!environment) {
    toast.error("Error", {
      description: `No pending environment to review exists at \`${params.projectSlug}/${params.envSlug}\` `,
      closeButton: true
    });
    throw redirect("/");
  }

  const formData = await request.formData();

  type Input = RequestInput<
    "post",
    "/api/projects/{slug}/environment-details/{env_slug}/review-preview-deployment/"
  >;
  const userData = {
    decision: formData.get("decision")?.toString()! as Input["decision"]
  } satisfies RequestInput<
    "post",
    "/api/projects/{slug}/environment-details/{env_slug}/review-preview-deployment/"
  >;
  const { error } = await apiClient.POST(
    "/api/projects/{slug}/environment-details/{env_slug}/review-preview-deployment/",
    {
      params: {
        path: {
          slug: params.projectSlug,
          env_slug: params.envSlug
        }
      },
      body: userData
    }
  );

  if (error) {
    const fullErrorMessage = error.errors.map((err) => err.detail).join(" ");

    toast.error("Error", {
      description: fullErrorMessage,
      closeButton: true
    });
    return {
      errors: error,
      userData
    };
  }

  await queryClient.invalidateQueries(
    environmentQueries.single(params.projectSlug, params.envSlug)
  );

  throw redirect(environment.preview_metadata!.external_url);
}
