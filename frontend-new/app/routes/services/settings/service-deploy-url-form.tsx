import {
  CheckIcon,
  CopyIcon,
  EyeIcon,
  EyeOffIcon,
  RefreshCcwIcon
} from "lucide-react";
import * as React from "react";
import { useFetcher } from "react-router";
import { Button, SubmitButton } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { cn } from "~/lib/utils";
import {
  type clientAction,
  useServiceQuery
} from "~/routes/services/settings/services-settings";
import { wait } from "~/utils";

export type ServiceDeployURLFormProps = {
  service_slug: string;
  project_slug: string;
};

export function ServiceDeployURLForm({
  project_slug,
  service_slug
}: ServiceDeployURLFormProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const [isDeployURLShown, setIsDeployURLShown] = React.useState(false);
  const [hasCopied, startTransition] = React.useTransition();
  const isPending = fetcher.state !== "idle";
  const { data: service } = useServiceQuery({
    project_slug,
    service_slug
  });
  const currentURL = new URL(window.location.href);
  const deployURL = service.deploy_token
    ? `${currentURL.protocol}//${currentURL.host}/api/deploy-service/docker/${service.deploy_token}`
    : null;

  return (
    <div className="w-full max-w-4xl">
      <fetcher.Form
        method="post"
        className="flex flex-col md:flex-row gap-2 w-full"
      >
        <fieldset className="w-full flex flex-col gap-5">
          <legend className="text-lg">Deploy webhook URL</legend>
          <p className="text-gray-400">
            Your private URL to trigger a deploy for this server. Remember to
            keep this a secret.
          </p>
          <div className="flex flex-col md:flex-row gap-2 md:items-start items-stretch">
            <span
              className={cn(
                "inline-flex flex-1 bg-muted rounded-md py-2 px-3 items-baseline",
                isDeployURLShown
                  ? "text-card-foreground"
                  : "text-muted-foreground"
              )}
            >
              {deployURL
                ? isDeployURLShown
                  ? deployURL
                  : "********************************************************************************"
                : ""}
            </span>

            <div className="flex gap-2">
              <TooltipProvider>
                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <Button
                      variant="outline"
                      className="p-4 self-start"
                      type="button"
                      disabled={!deployURL}
                      onClick={() => {
                        if (deployURL) {
                          navigator.clipboard.writeText(deployURL).then(() => {
                            // show pending state (which is success state), until the user has stopped clicking the button
                            startTransition(() => wait(1000));
                          });
                        }
                      }}
                    >
                      {hasCopied ? (
                        <CheckIcon size={15} className="flex-none" />
                      ) : (
                        <CopyIcon size={15} className="flex-none" />
                      )}
                      <span className="sr-only">Copy url</span>
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Copy url</TooltipContent>
                </Tooltip>
                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <SubmitButton
                      variant="outline"
                      isPending={isPending}
                      className="p-4"
                      name="intent"
                      value="regenerate-deploy-token"
                    >
                      <RefreshCcwIcon
                        size={15}
                        className={cn("flex-none", isPending && "animate-spin")}
                      />
                    </SubmitButton>
                  </TooltipTrigger>
                  <TooltipContent>regenerate URL</TooltipContent>
                </Tooltip>

                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <Button
                      variant="outline"
                      type="button"
                      onClick={() => setIsDeployURLShown(!isDeployURLShown)}
                      className="p-4"
                    >
                      {isDeployURLShown ? (
                        <EyeOffIcon size={15} className="flex-none" />
                      ) : (
                        <EyeIcon size={15} className="flex-none" />
                      )}
                      <span className="sr-only">
                        {isDeployURLShown ? "Hide" : "Show"} URL
                      </span>
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    {isDeployURLShown ? "Hide" : "Show"} URL
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </div>
        </fieldset>
      </fetcher.Form>
    </div>
  );
}
