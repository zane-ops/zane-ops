import { type VariantProps, cva } from "class-variance-authority";
import type * as React from "react";

import { cn } from "~/lib/utils";

const alertVariants = cva(
  "relative text-start w-full rounded-lg border p-4 [&>svg~*]:pl-7 [&>svg+div]:translate-y-[-3px] [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-5",
  {
    variants: {
      variant: {
        default: "bg-background text-foreground border-foreground",
        warning:
          "border-amber-600 text-white bg-amber-600 dark:bg-yellow-800 dark:border-transparent",
        success:
          "border-teal-500 text-teal-500 bg-teal-500/10 [&_[data-slot='description']]:text-card-foreground",
        info: "border-link text-link bg-link/10 [&_[data-slot='description']]:text-card-foreground",
        destructive:
          "border-destructive/50 text-destructive dark:border-destructive bg-destructive/10 [&>svg]:text-destructive [&_[data-slot='description']]:text-card-foreground",
        danger:
          "border-none text-white [&>svg]:text-white bg-destructive dark:bg-red-800"
      }
    },
    defaultVariants: {
      variant: "default"
    }
  }
);

const Alert = ({
  className,
  variant,
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof alertVariants>) => (
  <div
    role="alert"
    className={cn(alertVariants({ variant }), className)}
    {...props}
  />
);
Alert.displayName = "Alert";

function AlertTitle({
  ref,
  className,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement> & {
  ref?: React.RefObject<HTMLParagraphElement>;
}) {
  return (
    <h5
      ref={ref}
      data-slot="title"
      className={cn(
        "mb-1 font-semibold leading-none tracking-tight",
        className
      )}
      {...props}
    />
  );
}

const AlertDescription = ({
  ref,
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement> & {
  ref?: React.RefObject<HTMLParagraphElement>;
}) => (
  <div
    ref={ref}
    data-slot="description"
    className={cn("text-sm [&_p]:leading-relaxed", className)}
    {...props}
  />
);
AlertDescription.displayName = "AlertDescription";

export { Alert, AlertTitle, AlertDescription };
