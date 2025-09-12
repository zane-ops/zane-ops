import { EyeIcon, EyeOffIcon } from "lucide-react";
import React from "react";
import { Button } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { cn } from "~/lib/utils";

export function HidableInput({
  label,
  className,
  ...props
}: React.ComponentPropsWithRef<typeof Input> & { label?: string }) {
  const [isVisible, setIsVisible] = React.useState(false);

  return (
    <div className="flex items-center gap-2">
      <Input
        {...props}
        type={isVisible ? (props.type ?? "text") : "password"}
        className={cn("flex-1", className)}
      />
      <TooltipProvider>
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <Button
              variant="outline"
              type="button"
              onClick={() => setIsVisible((v) => !v)}
              className="p-4"
            >
              {isVisible ? (
                <EyeOffIcon size={15} className="flex-none" />
              ) : (
                <EyeIcon size={15} className="flex-none" />
              )}
              <span className="sr-only">
                {isVisible ? "Hide" : "Show"}
                {label && ` ${label}`}
              </span>
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            {isVisible ? "Hide" : "Show"}
            {label && ` ${label}`}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>
  );
}
