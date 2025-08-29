import { useQuery } from "@tanstack/react-query";
import { LockKeyholeIcon, SirenIcon } from "lucide-react";
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
  params,
  loaderData
}: Route.ComponentProps) {
  const { data: environment } = useQuery({
    ...environmentQueries.pendingReview(params.projectSlug, params.envSlug),
    initialData: loaderData.environment
  });

  const preview_meta = environment.preview_metadata!;

  const path = new URL(preview_meta.head_repository_url).pathname
    .substring(1)
    .replace(/\.git$/, "");

  const request_name = preview_meta.git_app?.gitlab
    ? "merge request"
    : "pull request";

  const navigation = useNavigation();

  return (
    <section className="size-full grow flex flex-col gap-6 items-center justify-center absolute inset-0 px-8">
      <div className="flex items-center gap-4">
        <GithubLogo className="size-18 flex-none" />
        <div className="flex items-center gap-2">
          <hr className="h-px max-w-40 w-20 border-dashed border border-grey" />
          <LockKeyholeIcon size={32} className="flex-none" />
          <hr className="h-px max-w-40 w-20 border-dashed border border-grey" />
        </div>
        <ThemedLogo className="size-24 flex-none" />
      </div>
      <h1 className="text-2xl font-medium flex items-center flex-wrap gap-0.5">
        <SirenIcon className="text-red-400 relative bottom-0.5" size={32} />
        <span>Preview Deployment Blocked</span>
        <SirenIcon className="text-red-400 relative bottom-0.5" size={32} />
      </h1>
      <div className="flex flex-col gap-4 text-grey">
        <p className="text-center">
          The preview deployment for {request_name}{" "}
          <a
            href={preview_meta.external_url}
            target="_blank"
            className="text-link"
          >
            {path}#{preview_meta.pr_number}
          </a>{" "}
          has been blocked and is awaiting authorization to be deployed.
        </p>

        <p className="text-center">
          As a member of this ZaneOps instance, please{" "}
          <a
            href={preview_meta.external_url}
            target="_blank"
            className="text-link"
          >
            review the {request_name}
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
        className="flex flex-col md:flex-row items-center gap-4 my-10"
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
  throw redirect(href("/project/:projectSlug/:envSlug", params));
}
