import {
  ChevronRightIcon,
  CircleCheckBigIcon,
  LoaderIcon,
  TriangleAlertIcon,
  Undo2Icon
} from "lucide-react";
import React from "react";
import { href, useFetcher, useNavigate } from "react-router";
import type { ComposeStack } from "~/api/types";
import { EnvVariableChangeItem } from "~/components/change-fields";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
import { Button, SubmitButton } from "~/components/ui/button";
import { PatchCodeEditor } from "~/components/ui/code-editor";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "~/components/ui/dialog";
import {
  FieldSet,
  FieldSetCheckbox,
  FieldSetLabel
} from "~/components/ui/fieldset";
import { Input } from "~/components/ui/input";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import type { clientAction } from "~/routes/compose/deploy-compose-stack";
import { capitalizeText, pluralize } from "~/utils";

export type ComposeStackChangesModalProps = {
  stack: ComposeStack;
  projectSlug: string;
  envSlug: string;
};

export function ComposeStackChangesModal({
  stack,
  ...params
}: ComposeStackChangesModalProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const [isOpen, setIsOpen] = React.useState(false);
  const isDeploying = fetcher.state !== "idle";
  const navigate = useNavigate();

  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);

  React.useEffect(() => {
    if (fetcher.state === "idle" && fetcher.data) {
      if (!fetcher.data.errors) {
        setIsOpen(false);
        navigate(
          href(
            "/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug/deployments",
            {
              ...params,
              composeStackSlug: stack.slug
            }
          )
        );
      }
    }
  }, [fetcher.data, fetcher.state]);

  const stackChangeGroups = Object.groupBy(
    stack.unapplied_changes,
    ({ field }) => field
  );
  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        {stack.unapplied_changes.length === 0 ? (
          <Button variant="ghost">
            <CircleCheckBigIcon size={15} />
            <span className="ml-1 underline">No pending changes</span>
          </Button>
        ) : (
          <Button variant="warning">
            <TriangleAlertIcon size={15} />
            <span className="mx-1">
              {stack.unapplied_changes.length}&nbsp;
              {pluralize("pending change", stack.unapplied_changes.length)}
            </span>
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-w-[min(var(--container-4xl),calc(100%_-_var(--spacing)*8))] gap-0">
        <DialogHeader className="pb-4">
          <DialogTitle>
            {stack.unapplied_changes.length === 0 ? (
              "no changes to apply"
            ) : (
              <>
                {stack.unapplied_changes.length}&nbsp;
                {pluralize("change", stack.unapplied_changes.length)}&nbsp;to
                apply
              </>
            )}
          </DialogTitle>
        </DialogHeader>
        {stack.unapplied_changes.length === 0 && (
          <div className="border-t border-border -mx-6 px-6 py-4">
            <div
              className={cn(
                "border-dashed border border-foreground rounded-md px-4 py-8 font-mono",
                "flex items-center justify-center text-foreground h-100"
              )}
            >
              No changes queued
            </div>
          </div>
        )}
        {stack.unapplied_changes.length > 0 && (
          <Accordion
            type="multiple"
            className="border-t border-border -mx-6 px-6 flex flex-col gap-2 h-100 overflow-auto py-4"
          >
            {Object.entries(stackChangeGroups).map((item) => {
              const field = item[0] as keyof typeof stackChangeGroups;
              const changes = item[1] as NonNullable<
                (typeof stackChangeGroups)[typeof field]
              >;
              const fieldNames: Record<keyof typeof stackChangeGroups, string> =
                {
                  compose_content: "Compose stack file contents",
                  env_overrides: "Environment overrides"
                };
              return (
                <div className="relative" key={field}>
                  <DiscardMultipleForm changes={changes} />
                  <AccordionItem
                    value={field}
                    className="flex flex-col border rounded-md relative"
                  >
                    <AccordionTrigger className="text-lg flex gap-2 items-center py-2 border-border bg-muted px-4">
                      <ChevronRightIcon
                        size={15}
                        className="flex-none text-grey"
                      />
                      <span>{fieldNames[field]}</span>
                      <small className="text-grey">
                        {changes.length} {pluralize("change", changes.length)}
                        &nbsp;will be applied
                      </small>
                    </AccordionTrigger>
                    <AccordionContent className="py-4 flex flex-col gap-2 px-4">
                      {field === "env_overrides" &&
                        changes.map((change) => (
                          <ChangeForm key={change.id} change_id={change.id}>
                            <EnvVariableChangeItem
                              change={change}
                              key={change.id}
                              unapplied
                            />
                          </ChangeForm>
                        ))}
                      {field === "compose_content" && (
                        <ChangeForm change_id={changes[0].id}>
                          <PatchCodeEditor
                            original={(changes[0].old_value as string) ?? ""}
                            modified={changes[0].new_value as string}
                            filename="docker-compose.yml"
                          />
                        </ChangeForm>
                      )}
                    </AccordionContent>
                  </AccordionItem>
                </div>
              );
            })}
          </Accordion>
        )}
        <DialogFooter className="border-t border-border -mx-6 px-6 pt-4">
          <fetcher.Form
            className="flex items-end gap-4 w-full"
            method="post"
            action="./deploy"
          >
            <div className="flex flex-col gap-3 w-full">
              <h3 className="text-lg dark:text-card-foreground">Deploy now</h3>

              <FieldSet
                errors={errors.commit_message}
                className="flex flex-col gap-1 w-full"
              >
                <FieldSetLabel htmlFor="commit_message">
                  Commit message
                </FieldSetLabel>
                <Input
                  id="commit_message"
                  name="commit_message"
                  placeholder="commit message for deployment"
                />
              </FieldSet>
            </div>

            <SubmitButton isPending={isDeploying} variant="secondary">
              {isDeploying ? (
                <>
                  <span>Deploying</span>
                  <LoaderIcon className="animate-spin" size={15} />
                </>
              ) : (
                "Deploy now"
              )}
            </SubmitButton>
          </fetcher.Form>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DiscardMultipleForm({
  changes
}: { changes: ComposeStack["unapplied_changes"] }) {
  const fetcher = useFetcher();
  const isPending = fetcher.state !== "idle";
  return (
    <fetcher.Form
      method="post"
      action="./discard-multiple-changes"
      className="absolute right-4 z-10 top-1"
    >
      {changes.map((ch) => (
        <input type="hidden" name="change_id" value={ch.id} />
      ))}
      <SubmitButton
        isPending={isPending}
        className="bg-transparent"
        variant="outline"
        size="sm"
      >
        {isPending ? (
          <>
            <LoaderIcon className="animate-spin" size={15} />
            <span>Discarding...</span>
          </>
        ) : (
          <>
            <Undo2Icon size={15} className="flex-none" />
            <span>Discard all</span>
          </>
        )}
      </SubmitButton>
    </fetcher.Form>
  );
}

function ChangeForm({
  change_id,
  children
}: { change_id: string; children: React.ReactNode }) {
  const fetcher = useFetcher();
  const isLoading = fetcher.state !== "idle";
  return (
    <fetcher.Form
      method="post"
      action="./discard-change"
      key={change_id}
      className="flex flex-col gap-3"
    >
      <input type="hidden" name="change_id" value={change_id} />
      {children}
      <hr className="border border-dashed border-border" />
      <SubmitButton
        isPending={isLoading}
        variant="outline"
        name="intent"
        value="cancel-service-change"
        className="self-end"
      >
        {isLoading ? (
          <>
            <LoaderIcon className="animate-spin" size={15} />
            <span>Discarding...</span>
          </>
        ) : (
          <>
            <Undo2Icon size={15} className="flex-none" />
            <span>Discard</span>
          </>
        )}
      </SubmitButton>
    </fetcher.Form>
  );
}
