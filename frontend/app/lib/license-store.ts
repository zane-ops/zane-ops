import { hashKey } from "@tanstack/react-query";
import { create } from "zustand";
import type { AuthedUserResponse, License } from "~/api/types";
import { createDevLogger } from "~/lib/logger";
import { licenseQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { syncWorkspaceStore } from "~/lib/workspace-store";

const logger = createDevLogger(import.meta.url);

type LicenseStore = {
  license: License | null;
};

export const useLicenseStore = create<LicenseStore>(() => ({
  license: null
}));

const licenseHash = hashKey(licenseQueries.get.queryKey);

export function syncLicenseStore(data: License | undefined | null) {
  logger.info({ data });
  useLicenseStore.setState({
    license: data ?? null
  });
}

getQueryClient()
  .getQueryCache()
  .subscribe((event) => {
    // We don't subscribe to `removed` event because
    // if we query is removed, normally the page should get updated before
    // components, but while the page is loading, this component get updated and rerender all its subscribers
    if (event.type !== "removed" && event.query.queryHash === licenseHash) {
      logger.scope("getQueryClient", "subscribe").info({ event });
      syncLicenseStore(event.query.state.data as License | undefined);
    }
  });
