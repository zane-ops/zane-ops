import { CheckIcon, LoaderIcon, PencilLineIcon, XIcon } from "lucide-react";
import * as React from "react";
import { flushSync } from "react-dom";
import { href, useFetcher, useNavigate } from "react-router";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import type { clientAction } from "~/routes/compose/compose-stack-settings";

export type ComposeStackSlugFormProps = {
  project_slug: string;
  env_slug: string;
  stack_slug: string;
};

export function ComposeStackSlugForm({
  project_slug,
  env_slug,
  stack_slug
}: ComposeStackSlugFormProps) {
  const [isEditing, setIsEditing] = React.useState(false);
  const fetcher = useFetcher<typeof clientAction>();
  const isPending = fetcher.state !== "idle";
  const navigate = useNavigate();
  const [data, setData] = React.useState(fetcher.data);
  const errors = getFormErrorsFromResponseData(data?.errors);
  const inputRef = React.useRef<React.ComponentRef<"input">>(null);

  React.useEffect(() => {
    setData(fetcher.data);

    const newSlug = fetcher.data?.data?.slug;
    if (fetcher.state === "idle" && newSlug) {
      navigate(
        href(
          "/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug/settings",
          {
            projectSlug: project_slug,
            envSlug: env_slug,
            composeStackSlug: newSlug
          }
        ),
        {
          replace: true,
          relative: "path"
        }
      );
      setIsEditing(false);
    }
  }, [fetcher.state, fetcher.data, project_slug, env_slug]);

  return (
    <div className="w-full max-w-4xl">
      <fetcher.Form
        method="post"
        className="flex flex-col md:flex-row gap-2 w-full"
      >
        <FieldSet
          name="slug"
          errors={errors.non_field_errors || errors.slug}
          className="flex flex-col gap-1.5 flex-1"
        >
          <FieldSetLabel htmlFor="slug">Compose Stack slug</FieldSetLabel>
          <div className="relative">
            <FieldSetInput
              ref={inputRef}
              placeholder="ex: uptime-kuma"
              defaultValue={stack_slug}
              disabled={!isEditing}
              className={cn(
                "disabled:placeholder-shown:font-mono disabled:bg-muted",
                "disabled:border-transparent disabled:opacity-100"
              )}
            />

            {!isEditing && (
              <Button
                variant="outline"
                onClick={() => {
                  flushSync(() => {
                    setIsEditing(true);
                  });
                  inputRef.current?.focus();
                }}
                className={cn(
                  "absolute inset-y-0 right-0 text-sm py-0 border-0",
                  "bg-inherit inline-flex items-center gap-2 border-muted-foreground py-0.5"
                )}
              >
                <span>Edit</span>
                <PencilLineIcon size={15} />
              </Button>
            )}
          </div>
        </FieldSet>

        {isEditing && (
          <div className="flex gap-2 md:relative top-8">
            <SubmitButton
              isPending={isPending}
              variant="outline"
              className="bg-inherit"
              name="intent"
              value="update-slug"
            >
              {isPending ? (
                <>
                  <LoaderIcon className="animate-spin" size={15} />
                  <span className="sr-only">Updating service slug...</span>
                </>
              ) : (
                <>
                  <CheckIcon size={15} className="flex-none" />
                  <span className="sr-only">Update service slug</span>
                </>
              )}
            </SubmitButton>
            <Button
              onClick={(ev) => {
                ev.currentTarget.form?.reset();
                setIsEditing(false);
                setData(undefined);
              }}
              variant="outline"
              className="bg-inherit"
              type="reset"
            >
              <XIcon size={15} className="flex-none" />
              <span className="sr-only">Cancel</span>
            </Button>
          </div>
        )}
      </fetcher.Form>
    </div>
  );
}
