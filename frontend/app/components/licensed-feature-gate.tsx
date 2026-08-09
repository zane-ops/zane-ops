import { CircleFadingArrowUpIcon, ClockFadingIcon } from "lucide-react";
import type * as React from "react";
import { Link, href } from "react-router";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { type Feature, useLicensedFeatureAccess } from "~/lib/licensed-feature";

export type LicensedFeatureGateProps = {
  feature: Feature;
  children: React.ReactNode;
  /**
   * What to render instead of `children` when the feature is locked.
   *
   * Defaults to `children` wrapped in a tooltip explaining what's needed to
   * unlock them, pass `null` to hide them entirely.
   */
  fallback?: React.ReactNode;
};

/**
 * Renders `children` only if the installed license unlocks `feature`.
 *
 * By default a locked feature is still shown, but inert and with a tooltip
 * telling the user what unlocks it, because silently removing it means they
 * never find out it exists in the first place.
 */
export function LicensedFeatureGate({
  feature,
  children,
  fallback
}: LicensedFeatureGateProps) {
  const access = useLicensedFeatureAccess(feature);

  if (access.allowed) return children;
  if (fallback !== undefined) return fallback;

  return (
    <TooltipProvider>
      <Tooltip delayDuration={0}>
        <TooltipTrigger asChild>
          {/* the trigger itself can't be `inert`, or it would stop receiving
              the hover events the tooltip needs */}
          <span className="inline-flex opacity-50 cursor-not-allowed">
            <span inert>{children}</span>
          </span>
        </TooltipTrigger>
        <TooltipContent className="max-w-64 flex items-start gap-2">
          {access.reason === "expired" ? (
            <>
              <ClockFadingIcon className="size-3.5 flex-none relative top-1 text-red-400" />
              <p className="text-red-400">Your license has expired</p>
            </>
          ) : (
            <>
              <CircleFadingArrowUpIcon className="size-3.5 flex-none relative top-1" />
              <p className="">
                Purchase a License with the{" "}
                <Link
                  to={href("/admin/license")}
                  className="text-link underline"
                >
                  {access.requiredTiersLabel}
                </Link>{" "}
                plan to use this feature.
              </p>
            </>
          )}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
