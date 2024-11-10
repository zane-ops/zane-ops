type UnionToIntersection<U> = (U extends any ? (k: U) => void : never) extends (
  k: infer I
) => void
  ? I
  : never;

export type MergeUnions<U> = UnionToIntersection<U> extends infer O
  ? { [K in keyof O]: O[K] }
  : never;

export type RecursivePartial<T> = {
  [P in keyof T]?: T[P] extends (infer U)[]
    ? RecursivePartial<U>[]
    : T[P] extends object
      ? RecursivePartial<T[P]>
      : T[P];
};
export type DotNotationToObject<
  T extends string,
  TValue extends unknown
> = T extends `${infer Head}.${infer Rest}`
  ? { [K in Head]: DotNotationToObject<Rest, TValue> }
  : { [K in T]: TValue };

type GetEventHandlers<T extends keyof JSX.IntrinsicElements> = Extract<
  keyof JSX.IntrinsicElements[T],
  `on${string}`
>;

/**
 * Provides the event type for a given element and handler.
 *
 * @example
 *
 * type MyEvent = EventFor<"input", "onChange">;
 */
export type EventFor<
  TElement extends keyof JSX.IntrinsicElements,
  THandler extends GetEventHandlers<TElement>
> = JSX.IntrinsicElements[TElement][THandler] extends
  | ((e: infer TEvent) => any)
  | undefined
  ? TEvent
  : never;

export type Writeable<T> = { -readonly [P in keyof T]: T[P] };

export type ValueOf<T> = T[keyof T];

export type SearchParams = {
  [key: string]: string | string[] | undefined;
};

export type DatePreset = {
  label: string;
  from: Date;
  to: Date;
  shortcut: string;
};

export type Option = {
  label: string;
  value: string | boolean | number | undefined;
};

export type Input = {
  type: "input";
  options?: Option[];
};

export type Checkbox = {
  type: "checkbox";
  component?: (props: Option) => JSX.Element | null;
  options?: Option[];
};

export type Slider = {
  type: "slider";
  min: number;
  max: number;
  // if options is undefined, we will provide all the steps between min and max
  options?: Option[];
};

export type Timerange = {
  type: "timerange";
  options?: Option[]; // required for TS
  presets?: DatePreset[];
};

export type Base<TData> = {
  label: string;
  value: keyof TData;
  /**
   * Defines if the accordion in the filter bar is open by default
   */
  defaultOpen?: boolean;
  /**
   * Defines if the command input is disabled for this field
   */
  commandDisabled?: boolean;
};

export type DataTableCheckboxFilterField<TData> = Base<TData> & Checkbox;
export type DataTableSliderFilterField<TData> = Base<TData> & Slider;
export type DataTableInputFilterField<TData> = Base<TData> & Input;
export type DataTableTimerangeFilterField<TData> = Base<TData> & Timerange;

export type DataTableFilterField<TData> =
  | DataTableCheckboxFilterField<TData>
  | DataTableSliderFilterField<TData>
  | DataTableInputFilterField<TData>
  | DataTableTimerangeFilterField<TData>;
