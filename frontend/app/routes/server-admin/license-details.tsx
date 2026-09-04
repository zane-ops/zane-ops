import { useQuery } from "@tanstack/react-query";
import {
  CheckIcon,
  DollarSignIcon,
  ExternalLinkIcon,
  InfoIcon,
  KeyRoundIcon,
  LoaderIcon,
  PencilLineIcon,
  ScaleIcon,
  TriangleAlertIcon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { useFetcher } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import type { License } from "~/api/types";
import { CopyButton } from "~/components/copy-button";
import { SimpleConfirmationDialog } from "~/components/delete-confirmation-dialog";
import { StatusBadge } from "~/components/status-badge";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
import { Card, CardContent, CardFooter } from "~/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "~/components/ui/dialog";
import {
  FieldSet,
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
import { BUILD_EDITION, BUY_LICENSE_LINK } from "~/lib/constants";
import { syncLicenseStore } from "~/lib/license-store";
import { licenseQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  cn,
  formattedTime,
  getCsrfTokenHeader,
  getFormErrorsFromResponseData,
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
              <PencilLineIcon className="size-4" />
            </Button>
          </ActivateLicenseDialog>
        )}
      </div>
      <Separator />
      {license ? (
        <LicenseCard license={license} />
      ) : (
        <div className="text-grey border border-dashed border-border h-80 flex flex-col gap-2 items-center justify-center rounded-lg">
          <h3 className="text-lg">No license installed on this instance</h3>
          <ActivateLicenseDialog>
            <Button className="gap-2">
              <span>Activate license</span>
              <KeyRoundIcon className="size-4" />
            </Button>
          </ActivateLicenseDialog>

          <div className="flex gap-2 items-center">
            <Separator className="w-10 " />
            <small className="">or</small>
            <Separator className="w-10 " />
          </div>

          <div className="flex flex-col gap-1 items-center">
            <a
              href={BUY_LICENSE_LINK}
              target="_blank"
              className="text-link underline inline-flex gap-2 items-center"
            >
              Buy new license
              <ExternalLinkIcon className="size-4" />
            </a>
            <p className="text-sm w-40 text-center">
              Your license key will be emailed to you
            </p>
          </div>
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
              Your instance is licensed under the
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
      <CardFooter className="py-3 px-3 bg-gray-600/10 flex rounded-b-md">
        <UninstallLicenseConfirmDialog />
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
  const fetcher = useFetcher<typeof clientAction>();
  const [isOpen, setOpen] = React.useState(false);
  const isPending = fetcher.state !== "idle";
  const [data, setData] = React.useState(fetcher.data);

  const errors = getFormErrorsFromResponseData(data?.errors);

  const close = React.useCallback(() => {
    setOpen(false);
    setData(undefined);
  }, []);

  React.useEffect(() => {
    setData(fetcher.data);
    // eslint-disable-next-line react-hooks/exhaustive-deps
    if (fetcher.data?.data) {
      close();
    }
  }, [fetcher.state, fetcher.data, close]);

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (isPending) return;
        setOpen(open);
        if (!open) close();
      }}
    >
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent>
        <DialogHeader className="pb-0">
          <DialogTitle>
            {type === "install" ? (
              <>Activate a new license</>
            ) : (
              <>Install new license</>
            )}
          </DialogTitle>

          {type === "install" ? (
            <Alert variant="info" className="mt-5">
              <InfoIcon className="size-4" />
              <AlertTitle>License key required</AlertTitle>
              <AlertDescription>
                Enter your license key below to activate it on this instance and
                unlock the features included in your plan.
              </AlertDescription>
            </Alert>
          ) : (
            <Alert variant="warning" className="mt-5">
              <TriangleAlertIcon className="size-4" />
              <AlertTitle>This will replace your current license</AlertTitle>
              <AlertDescription>
                Installing a new license key will immediately deactivate your
                current license and switch this instance to the new license's
                plan and features.
              </AlertDescription>
            </Alert>
          )}
        </DialogHeader>

        <p>
          You can also{" "}
          <a
            href={BUY_LICENSE_LINK}
            target="_blank"
            className="text-link underline inline-flex gap-2 items-center"
          >
            buy a new license
            <ExternalLinkIcon className="size-4" />
          </a>{" "}
          if you don&apos;t have one yet, your license key will be emailed to
          you.
        </p>

        <fetcher.Form method="post" id="install-form">
          <input type="hidden" name="intent" value="install" />
          <FieldSet name="uuid" errors={errors.uuid} required>
            <FieldSetLabel>License Key</FieldSetLabel>
            <FieldSetInput placeholder="format: 00000000-0000-0000-0000-000000000000" />
          </FieldSet>
        </fetcher.Form>

        <DialogFooter className="-mx-6 px-6">
          <SubmitButton
            isPending={isPending}
            form="install-form"
            className={cn("inline-flex gap-1 items-center")}
          >
            {isPending ? (
              <>
                <LoaderIcon className="animate-spin flex-none" size={15} />
                <span>Installing...</span>
              </>
            ) : (
              <span>Install license</span>
            )}
          </SubmitButton>

          <Button
            variant="outline"
            type="button"
            disabled={isPending}
            onClick={() => setOpen(false)}
          >
            Cancel
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export type UninstallLicenseConfirmDialogProps = {};

export function UninstallLicenseConfirmDialog({}: UninstallLicenseConfirmDialogProps) {
  const fetcher = useFetcher<typeof clientAction>();

  return (
    <SimpleConfirmationDialog
      fetcher={fetcher}
      title="Uninstall this license?"
      message={
        <>
          This action <strong>CANNOT</strong> be undone. This will immediately
          deactivate your license and disable all the features included in your
          plan.
        </>
      }
      form={
        <fetcher.Form method="post">
          <input type="hidden" name="intent" value="uninstall" />
        </fetcher.Form>
      }
      trigger={
        <DialogTrigger asChild>
          <Button variant="destructive">Uninstall license</Button>
        </DialogTrigger>
      }
      confirmText="Uninstall license"
      pendingText="Uninstalling..."
    />
  );
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const formData = await request.formData();
  const intent = formData.get("intent")?.toString();

  switch (intent) {
    case "install":
      return installLicense(formData);
    case "uninstall":
      return uninstallLicense();
    default:
      throw new Error(`Invalid intent '${intent}'`);
  }
}

async function installLicense(formData: FormData) {
  const queryClient = getQueryClient();
  const { error: errors, data: license } = await apiClient.POST(
    "/api/license/install/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      body: {
        uuid: formData.get("uuid")?.toString() ?? ""
      }
    }
  );

  if (errors) {
    return { errors };
  }

  await queryClient.invalidateQueries(licenseQueries.get);
  toast.success("Success", {
    description:
      "License installed successfully, you can now benefit from all the features included in your plan.",
    closeButton: true
  });
  return { data: license, errors: undefined };
}

async function uninstallLicense() {
  const queryClient = getQueryClient();
  const { error: errors } = await apiClient.DELETE("/api/license/uninstall/", {
    headers: {
      ...(await getCsrfTokenHeader())
    }
  });

  if (errors) {
    return { errors };
  }

  await queryClient.invalidateQueries(licenseQueries.get);
  toast.success("Success", {
    description: "License uninstalled successfully",
    closeButton: true
  });
  return { data: { success: true }, errors: undefined };
}
