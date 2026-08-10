import { useQuery } from "@tanstack/react-query";
import { KeyRoundIcon, RefreshCwIcon } from "lucide-react";
import type * as React from "react";
import type { License } from "~/api/types";
import { Button } from "~/components/ui/button";
import { Card } from "~/components/ui/card";
import { Separator } from "~/components/ui/separator";
import { BUILD_EDITION } from "~/lib/constants";
import { syncLicenseStore } from "~/lib/license-store";
import { licenseQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { metaTitle, notFound } from "~/lib/utils";
import type { Route } from "./+types/license-details";

export function meta() {
  return [metaTitle("License")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({}: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  if (BUILD_EDITION !== "ee") {
    throw notFound("Oops");
  }
  const license = await queryClient.ensureQueryData(licenseQueries.get);
  syncLicenseStore(license);
  return { license };
}

export default function LicenseDetailsPage({
  loaderData
}: Route.ComponentProps) {
  const { data: license } = useQuery({
    ...licenseQueries.get,
    initialData: loaderData.license
  });

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">License</h2>

        {license && (
          <ActivateLicenseDialog type="reinstall">
            <Button className="gap-2" variant="secondary">
              <span>Install new license</span>
              <RefreshCwIcon className="size-4" />
            </Button>
          </ActivateLicenseDialog>
        )}
      </div>
      <Separator />
      <h3 className="text-grey">Manage your ZaneOps License</h3>
      {license ? (
        <LicenseCard license={license} />
      ) : (
        <div className="border border-dashed border-border h-64 flex flex-col gap-2 items-center justify-center rounded-lg">
          <h3 className="text-grey text-lg">
            No license installed on this instance
          </h3>
          <ActivateLicenseDialog>
            <Button className="gap-2">
              <span>Activate license</span>
              <KeyRoundIcon className="size-4" />
            </Button>
          </ActivateLicenseDialog>
        </div>
      )}
    </section>
  );
}

export type LicenseCardProps = {
  license: License;
};

export function LicenseCard({ license }: LicenseCardProps) {
  return <Card className="p-4"></Card>;
}

export type ActivateLicenseDialogProps = {
  children?: React.ReactNode;
  type?: "install" | "reinstall";
};

export function ActivateLicenseDialog({
  children,
  type = "install"
}: ActivateLicenseDialogProps) {
  return <>{children}</>;
}
