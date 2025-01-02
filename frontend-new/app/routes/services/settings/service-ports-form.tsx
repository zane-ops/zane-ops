import {
  ExternalLinkIcon,
  LoaderIcon,
  PlusIcon,
  TriangleAlertIcon
} from "lucide-react";
import * as React from "react";
import { useFetcher } from "react-router";
import { Code } from "~/components/code";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import { getFormErrorsFromResponseData } from "~/lib/utils";
import {
  type clientAction,
  useServiceQuery
} from "~/routes/services/settings/services-settings";

export type ServicePortsFormProps = {
  project_slug: string;
  service_slug: string;
};

export function ServicePortsForm({
  service_slug,
  project_slug
}: ServicePortsFormProps) {
  return (
    <div className="w-full max-w-4xl flex flex-col gap-5">
      <div className="flex flex-col gap-3">
        <h3 className="text-lg">Exposed ports</h3>
        <p className="text-gray-400">
          This makes the service reachable externally via the ports defined
          in&nbsp;
          <Code>host port</Code>. Using&nbsp;
          <Code>80</Code>
          &nbsp;or&nbsp;
          <Code>443</Code>
          &nbsp;will create a default URL for the service.
        </p>

        <Alert variant="warning">
          <TriangleAlertIcon size={15} />
          <AlertTitle>Warning</AlertTitle>
          <AlertDescription>
            Using a host value other than 80 or 443 will disable&nbsp;
            <a href="#" className="underline inline-flex gap-1 items-center">
              zero-downtime deployments <ExternalLinkIcon size={12} />
            </a>
            .
          </AlertDescription>
        </Alert>
      </div>

      <hr className="border-border" />
      <h3 className="text-lg">Add new port</h3>
      <NewServicePortForm />
    </div>
  );
}

function NewServicePortForm() {
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const fetcher = useFetcher<typeof clientAction>();
  const isPending = fetcher.state !== "idle";

  const [data, setData] = React.useState(fetcher.data);
  const errors = getFormErrorsFromResponseData(data?.errors);

  React.useEffect(() => {
    setData(fetcher.data);

    if (fetcher.state === "idle" && !fetcher.data?.errors) {
      formRef.current?.reset();
    }
  }, [fetcher.data]);
  return (
    <fetcher.Form
      method="post"
      ref={formRef}
      className="flex md:items-start gap-3 md:flex-row flex-col items-stretch"
    >
      <input type="hidden" name="change_field" value="ports" />
      <input type="hidden" name="change_type" value="ADD" />
      <fieldset className="flex-1 inline-flex flex-col gap-1">
        <label className="text-gray-400">Forwarded port</label>
        <Input
          placeholder="ex: 8080"
          name="forwarded"
          aria-invalid={Boolean(errors.new_value?.forwarded)}
          aria-labelledby="forwarded-error"
        />
        {errors.new_value?.forwarded && (
          <span id="forwarded-error" className="text-red-500 text-sm">
            {errors.new_value?.forwarded}
          </span>
        )}
      </fieldset>
      <fieldset className="flex-1 inline-flex flex-col gap-1">
        <label className="text-gray-400">Host port</label>
        <Input
          placeholder="ex: 80"
          defaultValue={80}
          name="host"
          aria-invalid={Boolean(errors.new_value?.host)}
          aria-labelledby="host-error"
        />

        {errors.new_value?.host && (
          <span id="host-error" className="text-red-500 text-sm">
            {errors.new_value?.host}
          </span>
        )}
      </fieldset>

      <div className="flex gap-3 items-center pt-7 w-full md:w-auto">
        <SubmitButton
          isPending={isPending}
          variant="secondary"
          className="inline-flex gap-1 flex-1"
          name="intent"
          value="request-service-change"
        >
          {isPending ? (
            <>
              <span>Adding...</span>
              <LoaderIcon className="animate-spin" size={15} />
            </>
          ) : (
            <>
              <span>Add</span>
              <PlusIcon size={15} />
            </>
          )}
        </SubmitButton>
        <Button
          onClick={() => {
            setData(undefined);
          }}
          variant="outline"
          type="reset"
          className="flex-1"
        >
          Reset
        </Button>
      </div>
    </fetcher.Form>
  );
}
