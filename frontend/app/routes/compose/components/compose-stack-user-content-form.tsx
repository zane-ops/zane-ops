import {
  CheckIcon,
  ExternalLinkIcon,
  LoaderIcon,
  LockKeyholeIcon,
  Undo2Icon
} from "lucide-react";
import * as React from "react";
import { useFetcher } from "react-router";
import type { ComposeStack } from "~/api/types";
import { Button, SubmitButton } from "~/components/ui/button";
import { CodeEditor } from "~/components/ui/code-editor";
import { FieldSet, FieldSetLabel } from "~/components/ui/fieldset";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import type { clientAction } from "~/routes/compose/compose-stack-settings";

export type ComposeStackUserContentFormProps = {
  stack: ComposeStack;
};

export function ComposeStackUserContentForm({
  stack
}: ComposeStackUserContentFormProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const [data, setData] = React.useState(fetcher.data);
  const formRef = React.useRef<React.ComponentRef<"form">>(null);

  React.useEffect(() => {
    if (fetcher.state === "idle" && fetcher.data) {
      if (!fetcher.data.errors) {
        formRef.current?.reset();
      }
    }
  }, [fetcher.data, fetcher.state]);

  React.useEffect(() => {
    setData(fetcher.data);
  }, [fetcher.data]);

  const composeContentChange = stack?.unapplied_changes.find(
    (change) => change.field === "compose_content"
  );
  const isEmptyChange =
    composeContentChange !== undefined &&
    composeContentChange.new_value === null;

  const contents = isEmptyChange
    ? ""
    : ((composeContentChange?.new_value as string) ?? stack?.user_content);

  const computedContents =
    stack.computed_content ??
    "# will be generated once the stack if first deployed";

  const errors = getFormErrorsFromResponseData(data?.errors);
  const isPending = fetcher.state !== "idle";

  const [userContent, setUserContent] = React.useState(contents);
  const [accordionValue, setAccordionValue] = React.useState<string[]>([]);

  return (
    <fetcher.Form
      ref={formRef}
      method="post"
      className="flex flex-col gap-4 w-full items-start max-w-4xl"
    >
      <input type="hidden" name="change_field" value="compose_content" />
      <input type="hidden" name="change_type" value="UPDATE" />

      {composeContentChange !== undefined && (
        <input type="hidden" name="change_id" value={composeContentChange.id} />
      )}

      <textarea
        name="user_content"
        className="sr-only"
        value={userContent}
        readOnly
      />

      <p className="text-gray-400">
        Define your services, networks, and volumes using a docker-compose.yml
        format. More info in{" "}
        <a
          href="#"
          target="_blank"
          className="text-link underline inline-flex gap-1"
        >
          the docs <ExternalLinkIcon className="size-4 flex-none" />
        </a>
      </p>

      <hr className="border-border w-full" />

      <div
        className={cn(
          "flex flex-col gap-4 w-full rounded-md p-2",
          composeContentChange && "bg-secondary-foreground"
        )}
      >
        <FieldSet
          name="user_content"
          required
          errors={errors.new_value}
          className="w-full flex flex-col gap-2"
        >
          <FieldSetLabel className="dark:text-card-foreground">
            Compose stack file contents
          </FieldSetLabel>

          <small className="text-grey">
            Your docker compose file, ZaneOps will process it and add the
            necessary configurations for deployment.
          </small>

          <CodeEditor
            hasError={!!errors.new_value}
            containerClassName="w-full h-100"
            language="yaml"
            value={userContent}
            readOnly={!!composeContentChange}
            onChange={(value) => setUserContent(value ?? "")}
          />
        </FieldSet>
      </div>

      <div className="inline-flex items-center gap-2 self-end">
        {composeContentChange !== undefined ? (
          <SubmitButton
            isPending={isPending}
            variant="outline"
            name="intent"
            value="cancel-stack-change"
            disabled // TODO: remove
          >
            {isPending ? (
              <>
                <LoaderIcon className="animate-spin" size={15} />
                <span>Discarding...</span>
              </>
            ) : (
              <>
                <Undo2Icon size={15} className="flex-none" />
                <span>Discard change</span>
              </>
            )}
          </SubmitButton>
        ) : (
          <>
            <SubmitButton
              isPending={isPending}
              variant="secondary"
              name="intent"
              value="request-service-change"
            >
              {isPending ? (
                <>
                  <LoaderIcon className="animate-spin" size={15} />
                  <span>Updating ...</span>
                </>
              ) : (
                <>
                  <CheckIcon size={15} className="flex-none" />
                  <span>Update</span>
                </>
              )}
            </SubmitButton>
            <Button
              variant="outline"
              onClick={() => setData(undefined)}
              type="reset"
              className="flex-1 md:flex-none"
            >
              Reset
            </Button>
          </>
        )}
      </div>

      <hr className="my-2 border-border w-full" />

      {/* Compose content */}
      <div className={cn("w-full p-2")}>
        <FieldSet className="w-full flex flex-col gap-2">
          <FieldSetLabel className="dark:text-card-foreground flex items-center gap-1">
            Computed stack file contents
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger>
                  <LockKeyholeIcon className="size-4 flex-none text-grey" />
                  <span className="sr-only">(This file is read only)</span>
                </TooltipTrigger>
                <TooltipContent>This file is read-only</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </FieldSetLabel>

          <small className="text-grey">
            The final compose file generated by ZaneOps after processing your
            configuration.
          </small>

          <CodeEditor
            hasError={!!errors.new_value}
            containerClassName="w-full h-100"
            language="yaml"
            value={computedContents}
            readOnly
            onChange={(value) => setUserContent(value ?? "")}
          />
        </FieldSet>
      </div>
    </fetcher.Form>
  );
}
