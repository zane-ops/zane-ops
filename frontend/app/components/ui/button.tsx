import { Slot } from "@radix-ui/react-slot";
import { type VariantProps, cva } from "class-variance-authority";
import * as React from "react";
import type { EventFor } from "~/lib/types";

import { cn } from "~/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline:
          "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
        warning: "text-black bg-yellow-300"
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3 text-sm",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10"
      }
    },
    defaultVariants: {
      variant: "default",
      size: "default"
    }
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  ref?: React.ComponentProps<"button">["ref"];
}

function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: ButtonProps) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      {...props}
      className={cn(buttonVariants({ variant, size }), className)}
    />
  );
}

export type SubmitButtonProps = Omit<ButtonProps, "asChild" | "type"> & {
  isPending: boolean;
};

function SubmitButton({
  className,
  variant,
  size,
  isPending,
  ref,
  ...props
}: SubmitButtonProps) {
  return (
    <button
      className={cn(
        buttonVariants({ variant, size }),
        "inline-flex items-center gap-1",
        className
      )}
      ref={ref}
      {...props}
      aria-disabled={isPending}
      onClick={(e: EventFor<"button", "onClick">) => {
        if (isPending) e.preventDefault();
      }}
      type="submit"
    />
  );
}

export { Button, buttonVariants, SubmitButton };
