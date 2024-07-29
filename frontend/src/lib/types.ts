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
