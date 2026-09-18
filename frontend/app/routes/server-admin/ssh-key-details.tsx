import { href, redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { sshKeysQueries, swarmQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { getCsrfTokenHeader } from "~/lib/utils";
import type { Route } from "./+types/ssh-key-details";

export async function clientLoader() {
  throw redirect(href("/admin/servers"));
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const formData = await request.formData();
  const intent = formData.get("intent")?.toString();

  switch (intent) {
    case "delete_ssh_key": {
      return deleteSSHKey(params.slug);
    }
    default: {
      throw new Error("Unexpected intent");
    }
  }
}

async function deleteSSHKey(slug: string) {
  const queryClient = getQueryClient();

  const { error: errors } = await apiClient.DELETE(
    "/api/shell/ssh-keys/{slug}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: { slug }
      }
    }
  );

  if (errors) {
    const fullErrorMessage = errors.errors
      .map((err) => (err.attr ? `${err.attr}: ` : "") + err.detail)
      .join(" ");

    toast.error("Could not delete the SSH key", {
      description: fullErrorMessage,
      closeButton: true
    });
    return { errors };
  }

  await Promise.all([
    queryClient.invalidateQueries(sshKeysQueries.list),
    queryClient.invalidateQueries({
      queryKey: swarmQueries.nodeList().queryKey.slice(0, 1)
    })
  ]);

  toast.success("SSH key deleted", {
    closeButton: true,
    description: (
      <span>
        The key&nbsp;<code>{slug}</code>&nbsp;can no longer be used to connect
        to servers.
      </span>
    )
  });

  return { data: null };
}
