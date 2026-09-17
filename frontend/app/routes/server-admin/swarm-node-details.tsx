import { useQuery } from "@tanstack/react-query";
import { FlameIcon, InfoIcon, KeyRoundIcon } from "lucide-react";
import { swarmQueries } from "~/lib/queries";
import type { Route } from "./+types/swarm-node-details";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  return;
}

export default function SwarmNodeDetailsPage({
  params,
  matches: {
    "3": { loaderData }
  }
}: Route.ComponentProps) {
  const { data: node } = useQuery({
    ...swarmQueries.singleNode(params.serverId),
    initialData: loaderData.node
  });

  return (
    <section className="flex flex-col gap-4">
      <h3 className="text-grey">Update the details of this workspace</h3>

      <div className="grid lg:grid-cols-12 gap-10 relative">
        <div className="lg:col-span-10 flex flex-col">
          <section id="details" className="flex gap-1 scroll-mt-20">
            <div className="w-16 hidden md:flex flex-col items-center">
              <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
                <InfoIcon size={15} className="flex-none text-grey" />
              </div>
              <div className="h-full border border-grey/50"></div>
            </div>

            <div className="w-full flex flex-col gap-5 pt-1 pb-8">
              <h2 className="text-lg text-grey">Details</h2>

              {/* <WorkspaceDetailsForm name={workspace.name} /> */}
            </div>
          </section>

          <section id="ssh-keys" className="flex gap-1 scroll-mt-20">
            <div className="w-16 hidden md:flex flex-col items-center">
              <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
                <KeyRoundIcon size={15} className="flex-none text-grey" />
              </div>
              <div className="h-full border border-grey/50"></div>
            </div>

            <div className="w-full flex flex-col gap-5 pt-1 pb-8">
              <h2 className="text-lg text-grey">SSH Keys</h2>

              {/* <WorkspaceDetailsForm name={workspace.name} /> */}
            </div>
          </section>

          <section id="danger" className="flex gap-1 scroll-mt-20">
            <div className="w-16 hidden md:flex flex-col items-center">
              <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-red-500">
                <FlameIcon size={15} className="flex-none text-red-500" />
              </div>
            </div>

            <div className="w-full flex flex-col gap-5 pt-1 pb-14">
              <h2 className="text-lg text-red-400">Danger Zone</h2>
              <div className="flex flex-col gap-4 items-start max-w-4xl w-full rounded-md border border-border py-4">
                <div className="flex md:flex-row gap-4 justify-between items-center w-full px-4">
                  <div className="flex flex-col gap-1">
                    <h3 className="text-lg font-medium">
                      Remove Server from cluster
                    </h3>
                    <p>Drain all services from this server and remove it from the cluster</p>
                  </div>
                  {/* <WorkspaceDeleteForm name={workspace.name} /> */}
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </section>
  );
}
