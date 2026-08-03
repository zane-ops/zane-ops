import { useSearchParams } from "react-router";
import { HttpLogRequestDetails } from "~/components/http-log-request-details";
import type { HttpLog } from "~/lib/queries";

export type HttpLogDetailsProps = {
  /**
   * The log matching the `request_id` search param, the panel is closed when there is none.
   */
  log: HttpLog | undefined | null;
};

export function HttpLogDetails({ log }: HttpLogDetailsProps) {
  const [searchParams, setSearchParams] = useSearchParams();

  return (
    <HttpLogRequestDetails
      open={Boolean(log)}
      log={log ?? undefined}
      onClose={() => {
        searchParams.delete("request_id");
        setSearchParams(searchParams, { replace: true });
      }}
    />
  );
}
