import { CheckIcon, CopyIcon } from "lucide-react";
import * as React from "react";
import { Button } from "~/components/ui/button";
import { cn } from "~/lib/utils";
import { wait } from "~/utils";

export type CopyButtonProps = Omit<
  React.ComponentProps<typeof Button>,
  "value"
> & {
  value: string;
  label: string;
};

export function CopyButton({
  value,
  label,
  className,
  ...props
}: CopyButtonProps) {
  const [hasCopied, startTransition] = React.useTransition();
  return (
    <Button
      variant="ghost"
      {...props}
      className={cn(
        "px-2.5 py-0.5",
        "focus-visible:opacity-100 group-hover:opacity-100",
        hasCopied ? "opacity-100" : "md:opacity-0",
        className
      )}
      onClick={() => {
        navigator.clipboard.writeText(value).then(() => {
          // show pending state (which is success state), until the user has stopped clicking the button
          startTransition(() => wait(1000));
        });
      }}
    >
      {hasCopied ? (
        <CheckIcon size={15} className="flex-none" />
      ) : (
        <CopyIcon size={15} className="flex-none" />
      )}
      <span className="sr-only">{label}</span>
    </Button>
  );
}
