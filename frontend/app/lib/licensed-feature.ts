import type { QueryClient } from "@tanstack/react-query";
import * as React from "react";
import type { License } from "~/api/types";
import { BUILD_EDITION } from "~/lib/constants";
import { syncLicenseStore, useLicenseStore } from "~/lib/license-store";
import { licenseQueries, serverQueries } from "~/lib/queries";
import { notFound } from "~/lib/utils";

type Tier = License["tier"];

const TIER_LABELS = {
  free: "Free",
  starter: "Starter"
} satisfies Record<Tier, string>;

const FEATURE_TIER_MATRIX = {
  "workspace:create": ["starter"]
} satisfies Record<string, Tier[]>;

export type Feature = keyof typeof FEATURE_TIER_MATRIX;

export type FeatureAccess = {
  feature: Feature;
  allowed: boolean;
  /** the tiers that include this feature */
  requiredTiers: readonly Tier[];
  /** those same tiers, ready to be shown to the user (`"Starter or Pro"`) */
  requiredTiersLabel: string;
  currentTier: Tier;
  /** `null` when `allowed` is `true` */
  reason: "edition" | "tier" | "expired" | null;
};

// conjunction: `"Starter and Free"`
// disjunction: `"Starter or Free"`
const tierListFormatter = new Intl.ListFormat("en", { type: "disjunction" });

function computeAccess(
  /** the tier the license was issued for, `null` when there is no license */
  licensedTier: Tier | null,
  isValid: boolean,
  feature: Feature
): FeatureAccess {
  const requiredTiers: readonly Tier[] = FEATURE_TIER_MATRIX[feature];
  // an invalid (expired or revoked) license grants nothing, it falls back to
  // `free` instead of keeping the tier it was issued for
  const currentTier = isValid && licensedTier ? licensedTier : "free";
  const allowed = requiredTiers.includes(currentTier);

  return {
    feature,
    allowed,
    requiredTiers,
    requiredTiersLabel: tierListFormatter.format(
      requiredTiers.map((tier) => TIER_LABELS[tier])
    ),
    currentTier,
    reason: allowed
      ? null
      : BUILD_EDITION !== "ee"
        ? "edition"
        : // the license *would* have covered this feature, it just isn't valid anymore
          licensedTier && requiredTiers.includes(licensedTier)
          ? "expired"
          : "tier"
  };
}

export function getFeatureAccess(
  license: License | null | undefined,
  feature: Feature
): FeatureAccess {
  return computeAccess(
    license?.tier ?? null,
    license?.is_valid ?? false,
    feature
  );
}

/**
 * Whether the installed license unlocks `feature`.
 *
 * This is the hook to reach for when all you need is to show or hide
 * something, use {@link useLicensedFeatureAccess} when you also want to tell the user
 * *why* they can't access it.
 */
export function useLicensedFeature(feature: Feature): boolean {
  return useLicensedFeatureAccess(feature).allowed;
}

/**
 * Same as {@link useLicensedFeature}, but returns the required/current tiers alongside
 * the verdict so the UI can render an "upgrade to X" call to action.
 *
 * Both tiers are subscribed to as primitives : the license store is rewritten
 * on every refetch of the license query, so selecting the whole object would
 * rerender every consumer even when nothing about the license changed.
 */
export function useLicensedFeatureAccess(feature: Feature): FeatureAccess {
  const tier = useLicenseStore((state) => state.license?.tier ?? null);
  const isValid = useLicenseStore((state) => state.license?.is_valid ?? false);

  return React.useMemo(
    () => computeAccess(tier, isValid, feature),
    [tier, isValid, feature]
  );
}

export async function ensureLicensedFeatureAvailability(
  queryClient: QueryClient,
  feature: Feature
) {
  const license =
    BUILD_EDITION === "ee"
      ? await queryClient.ensureQueryData(licenseQueries.get)
      : null;
  syncLicenseStore(license);

  const access = getFeatureAccess(license, feature);
  if (!access.allowed) {
    throw notFound(
      import.meta.env.DEV
        ? `Your license does not include this feature (requires the ${access.requiredTiersLabel} tier)`
        : "Not found"
    );
  }
  return access;
}
