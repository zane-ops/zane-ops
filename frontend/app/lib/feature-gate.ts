import * as React from "react";
import type { License } from "~/api/types";
import { useLicenseStore } from "~/lib/license-store";

const FEATURE_TIER_MATRIX = {
  CAN_CREATE_WORKSPACE: "starter"
} satisfies Record<string, License["tier"]>;

export function useFeatureGate() {
  const license = useLicenseStore((s) => s.license);

  return React.useCallback(
    (feature: keyof typeof FEATURE_TIER_MATRIX) => {
      return FEATURE_TIER_MATRIX[feature] === license?.tier;
    },
    [license]
  );
}
