import {
  CheckIcon,
  CopyIcon,
  ExternalLinkIcon,
  EyeIcon,
  EyeOffIcon,
  RefreshCcwIcon
} from "lucide-react";
import * as React from "react";
import { useFetcher } from "react-router";
import type { ComposeStack } from "~/api/types";
import { Button, SubmitButton } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { cn } from "~/lib/utils";
import type { clientAction } from "~/routes/compose/compose-stack-settings";
import { wait } from "~/utils";

export type ServiceDeployURLFormProps = {
  stack: ComposeStack;
};

export function ComposeStackDeployURLForm({
  stack
}: ServiceDeployURLFormProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const [isDeployURLShown, setIsDeployURLShown] = React.useState(false);
  const [hasCopied, startTransition] = React.useTransition();
  const isPending = fetcher.state !== "idle";

  const currentURL = new URL(window.location.href);
  const deployURL = stack.deploy_token
    ? `${currentURL.protocol}//${currentURL.host}/api/compose/deploy-stack/${stack.deploy_token}`
    : null;

  const inputRef = React.useRef<React.ComponentRef<"input">>(null);

  return (
    <div className="w-full max-w-4xl">
      <fetcher.Form
        method="post"
        className="flex flex-col md:flex-row gap-2 w-full"
        action="../regenerate-token"
      >
        <fieldset className="w-full flex flex-col gap-5">
          <legend>Deploy webhook URL</legend>
          <p className="text-gray-400 mt-2">
            Your private URL to&nbsp;
            <a
              href="https://zaneops.dev/api-reference/openapi/#tag/deploy-stack"
              target="_blank"
              className="text-link underline inline-flex gap-1 items-center"
            >
              trigger a new deployment <ExternalLinkIcon size={12} />
            </a>
            &nbsp;of this stack (e.g. from a CI/CD pipeline). Remember to keep
            this a secret.
          </p>
          <div className="flex flex-col md:flex-row gap-2 md:items-start items-stretch">
            <label htmlFor="deploy-url" className="sr-only">
              URL
            </label>
            <Input
              id="deploy-url"
              ref={inputRef}
              placeholder="<empty>"
              className="placeholder-shown:font-mono bg-muted opacity-100 disabled:cursor-default"
              value={deployURL ?? ""}
              readOnly
              type={isDeployURLShown ? "text" : "password"}
            />

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
                            inputRef.current?.select();
                          });
                        }
                      }}
                    >
                      {hasCopied ? (
                        <CheckIcon size={15} className="flex-none" />
                      ) : (
                        <CopyIcon size={15} className="flex-none" />
                      )}
                      <span className="sr-only">Copy URL</span>
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
                      <span className="sr-only">Regenerate URL</span>
                    </SubmitButton>
                  </TooltipTrigger>
                  <TooltipContent>Regenerate URL</TooltipContent>
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
