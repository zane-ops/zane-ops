import { useQuery } from "@tanstack/react-query";
import {
  CheckIcon,
  KeyRoundIcon,
  RefreshCwIcon,
  ScaleIcon,
  XIcon
} from "lucide-react";
import type * as React from "react";
import type { License } from "~/api/types";
import { StatusBadge } from "~/components/status-badge";
import { Button } from "~/components/ui/button";
import { Card, CardContent, CardFooter, CardTitle } from "~/components/ui/card";
import { Separator } from "~/components/ui/separator";
import { BUILD_EDITION } from "~/lib/constants";
import { syncLicenseStore } from "~/lib/license-store";
import { licenseQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { formattedTime, metaTitle, notFound } from "~/lib/utils";
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
      {/* <h3 className="text-grey">Manage your ZaneOps License</h3> */}
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
  return (
    <Card className="px-6 py-6 bg-toggle flex flex-col gap-1">
      <div className=" rounded-md">
        <div className="font-normal flex gap-3 items-center mb-4">
          <ScaleIcon className="size-9 flex-none" />
          <div className="flex flex-col gap-0">
            <span className="text-xs text-grey">
              Your host is licensed under the
            </span>
            <div className="flex items-center gap-2">
              <h3 className="capitalize font-medium text-2xl ">
                ZaneOps {license.tier} License{" "}
              </h3>
              {license.is_valid ? (
                <StatusBadge color="green" pingState="hidden" className="gap-1">
                  Valid
                  <CheckIcon className="flex-none size-4 text-teal-600 dark:text-teal-400" />
                </StatusBadge>
              ) : (
                <StatusBadge color="red" pingState="hidden" className="gap-1">
                  Invalid
                  <XIcon className="flex-none size-4 text-red-400" />
                </StatusBadge>
              )}
            </div>
          </div>
        </div>

        <CardContent className="px-0 py-4">
          <dl className="flex flex-col gap-2">
            <div>
              <dt className="font-medium">Instance Fingerprint:</dt>
              <dd className="text-grey">{license.instance_fingerprint}</dd>
            </div>
            <div>
              <dt className="font-medium">Expires At:</dt>
              <dd className="text-grey">
                <time dateTime={new Date(license.expires_at).toISOString()}>
                  {formattedTime(license.expires_at)}
                </time>
              </dd>
            </div>
            <div>
              <dt className="font-medium">License Key:</dt>
              <dd className="text-grey">{license.uuid}</dd>
            </div>
          </dl>
        </CardContent>
      </div>
      <CardFooter className="pt-6 pb-0 px-6 flex border-t border-border -mx-6">
        <Button variant="outline">Recheck license</Button>
      </CardFooter>
    </Card>
  );
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
