import { useQuery } from "@tanstack/react-query";
import { Separator } from "~/components/ui/separator";
import { sshKeysQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import type { Route } from "./+types/ssh-keys-settings";

export async function clientLoader() {
  const sshKeys = await queryClient.ensureQueryData(sshKeysQueries.list);
  return { sshKeys };
}

export default function SSHKeysPagePage({ loaderData }: Route.ComponentProps) {
  const { data: sshKeys } = useQuery({
    ...sshKeysQueries.list,
    initialData: loaderData.sshKeys
  });

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-2xl">SSH keys</h2>
      <Separator />
      <p className="text-sm">
        This is a list of SSH keys associated with your account. Remove any keys
        that you do not recognize.
      </p>
    </div>
  );
}
