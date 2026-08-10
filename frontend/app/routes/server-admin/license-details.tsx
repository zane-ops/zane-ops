import { useQuery } from "@tanstack/react-query";
import {
  CheckIcon,
  InfoIcon,
  KeyRoundIcon,
  RefreshCwIcon,
  ScaleIcon,
  XIcon
} from "lucide-react";
import type * as React from "react";
import type { License } from "~/api/types";
import { CopyButton } from "~/components/copy-button";
import { StatusBadge } from "~/components/status-badge";
import { Button } from "~/components/ui/button";
import { Card, CardContent, CardFooter, CardTitle } from "~/components/ui/card";
import { Separator } from "~/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { BUILD_EDITION } from "~/lib/constants";
import { syncLicenseStore } from "~/lib/license-store";
import { licenseQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  cn,
  formattedTime,
  metaTitle,
  notFound,
  relativeTimeFormatter
} from "~/lib/utils";
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
  const LICENSE_TIER_DESCRIPTION_MAP = {
    free: "This license lets you run a single workspace with up to 3 users on this instance.",
    starter:
      "This license allows you to run as many workspaces and invite as many users as you need on this instance."
  } satisfies Record<License["tier"], string>;
  return (
    <Card className="p-1 border-gray-600 flex flex-col gap-1  w-full border-dashed">
      <div className="bg-gray-600/10 p-4 rounded-t-md">
        <div className="font-normal flex gap-3 items-center mb-5">
          <ScaleIcon className="size-7 flex-none" />
          <div className="flex flex-col gap-0">
            <span className="text-xs text-grey">
              Your host is licensed under the
            </span>
            <div className="flex items-center gap-2">
              <h3 className="font-medium text-xl">
                ZaneOps{" "}
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger asChild>
                      <span className="capitalize cursor-help inline-flex items-center gap-1 underline decoration-wavy decoration-1">
                        {license.tier}
                      </span>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-64">
                      <p className="text-sm font-normal">
                        {LICENSE_TIER_DESCRIPTION_MAP[license.tier]}
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>{" "}
                License{" "}
              </h3>
              {license.is_valid ? (
                <StatusBadge color="green" pingState="hidden" className="gap-1">
                  Valid
                  <CheckIcon className="flex-none size-4 text-green-600" />
                </StatusBadge>
              ) : (
                <StatusBadge color="red" pingState="hidden" className="gap-1">
                  Invalid
                  <XIcon className="flex-none size-4 text-red-600" />
                </StatusBadge>
              )}
            </div>
          </div>
        </div>

        <CardContent className="px-0 pb-4 text-sm">
          <dl className="flex flex-col gap-2">
            <div>
              <dt>License Key:</dt>
              <dd className="text-grey flex items-center gap-2">
                <p className="truncate uppercase">{license.uuid}</p>
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger asChild>
                      <CopyButton
                        value={license.uuid}
                        label="Copy license key"
                        size="icon"
                        className="hover:bg-transparent !opacity-100 size-4"
                      />
                    </TooltipTrigger>
                    <TooltipContent className="capitalize">
                      Copy license key
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </dd>
            </div>

            <div>
              <dt>Instance Fingerprint:</dt>
              <dd className="text-grey w-full flex items-center gap-2">
                <p className="truncate">{license.instance_fingerprint}</p>
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger asChild>
                      <CopyButton
                        value={license.instance_fingerprint}
                        label="Copy instance fingerprint"
                        size="icon"
                        className="hover:bg-transparent !opacity-100 size-4"
                      />
                    </TooltipTrigger>
                    <TooltipContent className="capitalize">
                      Copy instance fingerprint
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </dd>
            </div>

            <div>
              <dt>Installed At:</dt>
              <dd className="text-grey">
                <time dateTime={new Date(license.expires_at).toISOString()}>
                  {formattedTime(license.installed_at)}
                </time>
              </dd>
            </div>

            <div>
              <dt>Expires At:</dt>
              <dd className="text-grey">
                <time dateTime={new Date(license.expires_at).toISOString()}>
                  {formattedTime(license.expires_at)} (
                  {relativeTimeFormatter(license.expires_at)})
                </time>
              </dd>
            </div>
          </dl>
        </CardContent>
      </div>
      <CardFooter className="py-2 px-3 bg-gray-600/10 flex rounded-b-md">
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
