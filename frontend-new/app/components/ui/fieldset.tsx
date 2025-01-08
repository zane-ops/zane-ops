import * as React from "react";
import { Checkbox } from "~/components/ui/checkbox";
import { Input } from "~/components/ui/input";
import { Select } from "~/components/ui/select";
import { Slider } from "~/components/ui/slider";

import { cn } from "~/lib/utils";

export type FieldSetProps = {
  errors?: string | string[];
  children: React.ReactNode;
} & React.ComponentProps<"fieldset">;

type FieldSetContext = {
  id: string;
  name?: string;
  errors?: string | string[];
};

const FieldSetContext = React.createContext<FieldSetContext | null>(null);

export function FieldSet({
  className,
  errors,
  children,
  name,
  ...props
}: FieldSetProps) {
  const id = React.useId();
  const childrenArray = React.Children.toArray(children);

  const isErrorComponentInChildren = childrenArray.some(
    (child) =>
      typeof child === "object" &&
      child !== null &&
      React.isValidElement(child) &&
      child.type === FieldSetErrors
  );

  return (
    <FieldSetContext value={{ id, errors, name }}>
      <fieldset className={className} {...props}>
        {children}
        {!isErrorComponentInChildren && errors && <FieldSetErrors />}
      </fieldset>
    </FieldSetContext>
  );
}

export function FieldSetErrors(
  props: Omit<React.ComponentProps<"span">, "id">
) {
  const ctx = React.use(FieldSetContext);
  if (!ctx) {
    throw new Error(
      "<FieldSetErrors> component should be inside of a <FieldSet> component"
    );
  }
  const { id, errors } = ctx;
  return (
    errors && (
      <span
        id={`${id}-error`}
        className={cn("text-red-500 text-sm", props.className)}
      >
        {errors}
      </span>
    )
  );
}

export function FieldSetLabel(
  props: Omit<React.ComponentProps<"label">, "htmlFor">
) {
  const ctx = React.use(FieldSetContext);
  if (!ctx) {
    throw new Error(
      "<FieldSetLabel> component should be inside of a <FieldSet> component"
    );
  }

  const { id } = ctx;
  return <label htmlFor={id} {...props} />;
}

export function FieldSetInput(
  props: Omit<
    React.ComponentProps<typeof Input>,
    "id" | "aria-invalid" | "aria-labelledby"
  >
) {
  const ctx = React.use(FieldSetContext);

  if (!ctx) {
    throw new Error(
      "<FieldSetInput> component should be inside of a <FieldSet> component"
    );
  }

  const { id, errors, name } = ctx;

  return (
    <Input
      id={id}
      aria-invalid={Boolean(errors)}
      aria-labelledby={`${id}-error`}
      {...props}
      name={props.name ?? name}
    />
  );
}

export function FieldSetCheckbox(
  props: Omit<
    React.ComponentProps<typeof Checkbox>,
    "id" | "aria-invalid" | "aria-labelledby"
  >
) {
  const ctx = React.use(FieldSetContext);

  if (!ctx) {
    throw new Error(
      "<FieldSetCheckbox> component should be inside of a <FieldSet> component"
    );
  }

  const { id, errors, name } = ctx;

  return (
    <Checkbox
      id={id}
      aria-invalid={Boolean(errors)}
      aria-labelledby={`${id}-error`}
      {...props}
      name={props.name ?? name}
    />
  );
}

export function FieldSetSelect(props: React.ComponentProps<typeof Select>) {
  const ctx = React.use(FieldSetContext);

  if (!ctx) {
    throw new Error(
      "<FieldSetSelect> component should be inside of a <FieldSet> component"
    );
  }

  const { id, errors } = ctx;
  return (
    <Select
      aria-invalid={Boolean(errors)}
      aria-labelledby={`${id}-error`}
      {...props}
    />
  );
}

export function FieldSetSlider(props: React.ComponentProps<typeof Slider>) {
  const ctx = React.use(FieldSetContext);

  if (!ctx) {
    throw new Error(
      "<FieldSetSelect> component should be inside of a <FieldSet> component"
    );
  }

  const { id, errors, name } = ctx;
  return (
    <Slider
      id={id}
      aria-invalid={Boolean(errors)}
      aria-labelledby={`${id}-error`}
      {...props}
      name={props.name ?? name}
    />
  );
}
