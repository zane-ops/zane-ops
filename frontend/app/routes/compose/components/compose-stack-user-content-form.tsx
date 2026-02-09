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
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
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

  const defaultContents = isEmptyChange
    ? ""
    : ((composeContentChange?.new_value as string) ?? stack?.user_content);

  const computedContents =
    stack.computed_content ??
    "# will be generated once the stack is first deployed";

  const errors = getFormErrorsFromResponseData(data?.errors);
  const isPending = fetcher.state !== "idle";

  const [userContent, setUserContent] = React.useState(defaultContents);
  const [accordionValue, setAccordionValue] = React.useState("");

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
          composeContentChange && "dark:bg-secondary-foreground bg-secondary/60"
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

          <p className="text-grey">
            Your docker compose file, ZaneOps will process it and add the
            necessary configurations for deployment.
          </p>

          <CodeEditor
            hasError={!!errors.new_value}
            containerClassName={cn(
              "w-full h-100",
              "w-[80dvw] sm:w-[88dvw] md:w-[82dvw] lg:w-[73dvw] xl:w-[890px]"
            )}
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
              value="request-stack-change"
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
              onClick={() => {
                setData(undefined);
                setUserContent(defaultContents);
              }}
              type="reset"
              className="flex-1 md:flex-none"
            >
              Reset
            </Button>
          </>
        )}
      </div>

      <hr className="my-2 border-border w-full" />

      {/* Computed Compose content */}
      <Accordion
        type="single"
        collapsible
        value={accordionValue}
        onValueChange={(state) => {
          setAccordionValue(state);
        }}
        className="w-full"
      >
        <AccordionItem value={`computed`} className="border-none">
          <AccordionTrigger
            className={cn(
              "rounded-md p-4 flex items-start gap-2 bg-muted",
              "aria-expanded:rounded-b-none"
            )}
          >
            <div className="flex flex-col gap-2">
              <h3 className="text-base inline-flex gap-1 items-center">
                <span>Computed stack file contents</span>
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger className="relative z-10">
                      <LockKeyholeIcon className="size-4 flex-none text-grey" />
                      <span className="sr-only">(This file is read only)</span>
                    </TooltipTrigger>
                    <TooltipContent>This file is read-only</TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </h3>
              <p className="text-grey text-start">
                The final compose file generated by ZaneOps after processing
                your configuration.
              </p>
            </div>
          </AccordionTrigger>
          <AccordionContent className="border-border border-x border-b rounded-b-md p-4 mb-4">
            <div className={cn("flex flex-col gap-4 w-full")}>
              <FieldSet className="flex flex-col gap-1.5 flex-1">
                <CodeEditor
                  containerClassName={cn(
                    "w-full h-100",
                    "w-[80dvw] sm:w-[88dvw] md:w-[85dvw] lg:w-[73dvw] xl:w-[860px]"
                  )}
                  language="yaml"
                  value={computedContents}
                  readOnly
                  onChange={(value) => setUserContent(value ?? "")}
                />
              </FieldSet>
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </fetcher.Form>
  );
}
