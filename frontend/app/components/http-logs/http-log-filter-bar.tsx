import { type UseQueryOptions, useQuery } from "@tanstack/react-query";
import { Maximize2Icon, Minimize2Icon, PlusIcon, XIcon } from "lucide-react";
import * as React from "react";
import type { DateRange } from "react-day-picker";
import { flushSync } from "react-dom";
import { useSearchParams } from "react-router";
import { useDebouncedCallback } from "use-debounce";
import { DateRangeWithShortcuts } from "~/components/date-range-with-shortcuts";
import {
  MultiSelect,
  type MultiSelectOption,
  getMultiSelectOptionValue
} from "~/components/multi-select";
import { Button } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { COUNTRY_CODE_LIST } from "~/lib/countryCodeList";
import {
  type HTTPLogFilters,
  type HttpLogFilterField,
  REQUEST_METHODS,
  httpLogSearchSchema
} from "~/lib/queries";
import type { Writeable } from "~/lib/types";

/**
 * Returns the query used to autocomplete the values of a filterable HTTP log field,
 * each page provides its own (service, deployment, compose stack, ...).
 */
export type HttpLogfieldValuesQuery = (params: {
  field: HttpLogFilterField;
  value: string;
}) => UseQueryOptions<string[], Error, string[], any>;

/**
 * Fields that can be added to the filter bar, mapped to the label shown in the
 * `Add Filter` dropdown.
 */
const FIELD_LABEL_MAP = {
  host: "request_host",
  path: "request_path",
  query: "request_query",
  "user agent": "request_user_agent",
  "client ip": "request_ip",
  status: "status",
  country: "request_country_code"
} as const satisfies Record<string, keyof HTTPLogFilters>;

const POSSIBLE_FIELDS = Object.values(FIELD_LABEL_MAP);

type PossibleField = (typeof POSSIBLE_FIELDS)[number];

function getActiveFields(search: HTTPLogFilters) {
  return POSSIBLE_FIELDS.filter((field) => {
    if (field === "request_query") {
      return field in search;
    }
    return field in search && (search[field]?.length ?? 0) > 0;
  });
}

export type HttpLogFilterBarProps = {
  fieldValuesQuery: HttpLogfieldValuesQuery;
  /**
   * Extra filters rendered after the built-in ones, ex: the stack services filter.
   */
  extraFilters?: React.ReactNode;
  /**
   * Search params that also count as active filters when computing whether
   * the `Reset filters` button should be shown, ex: `stack_service_name`.
   */
  extraFilterParamKeys?: string[];
};

export function HttpLogFilterBar({
  fieldValuesQuery,
  extraFilters,
  extraFilterParamKeys = []
}: HttpLogFilterBarProps) {
  const [, startTransition] = React.useTransition();
  const [searchParams, setSearchParams] = useSearchParams();
  const search = httpLogSearchSchema.parse(searchParams);

  const inputRef = React.useRef<React.ComponentRef<"input">>(null);

  const date: DateRange = {
    from: search.time_after,
    to: search.time_before
  };

  const [selectedFields, setSelectedFields] = React.useState(() =>
    getActiveFields(search)
  );

  const available_fields = POSSIBLE_FIELDS.filter(
    (field) => !selectedFields.includes(field)
  );

  const isEmptySearchParams =
    !search.time_after &&
    !search.time_before &&
    (search.sort_by ?? []).length === 0 &&
    (search.request_method ?? []).length === 0 &&
    extraFilterParamKeys.every(
      (key) => searchParams.getAll(key).length === 0
    ) &&
    POSSIBLE_FIELDS.every((field) => {
      if (field === "request_query") {
        return !(field in search);
      }
      return !(field in search) || (search[field]?.length ?? 0) === 0;
    });

  const clearFilters = () => {
    startTransition(() => {
      const newSearchParams = new URLSearchParams();
      if (searchParams.get("isMaximized")) {
        newSearchParams.set("isMaximized", `${search.isMaximized}`);
      }
      setSearchParams(newSearchParams, {
        replace: true
      });
      setSelectedFields([]);
    });

    if (inputRef.current) {
      inputRef.current.value = "";
    }
  };

  const searchForQuery = useDebouncedCallback((query: string) => {
    startTransition(() => {
      searchParams.set("request_query", query);
      setSearchParams(searchParams, { replace: true });
    });
  }, 300);

  const parentRef = React.useRef<React.ComponentRef<"section">>(null);

  React.useEffect(() => {
    setSelectedFields(getActiveFields(httpLogSearchSchema.parse(searchParams)));
  }, [searchParams]);

  const removeField = (field: PossibleField) => {
    setSelectedFields((fields) => fields.filter((item) => item !== field));
    searchParams.delete(field);
    setSearchParams(searchParams, { replace: true });
  };

  return (
    <>
      <section
        className="rounded-t-sm w-full flex gap-2 items-start justify-between"
        ref={parentRef}
      >
        <div className="flex items-center gap-2 flex-wrap">
          <TooltipProvider>
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  onClick={() => {
                    searchParams.set("isMaximized", `${!search.isMaximized}`);
                    setSearchParams(searchParams, { replace: true });
                  }}
                >
                  <span className="sr-only">
                    {search.isMaximized ? "Minimize" : "Maximize"}
                  </span>
                  {search.isMaximized ? (
                    <Minimize2Icon size={15} />
                  ) : (
                    <Maximize2Icon size={15} />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent className="max-w-64 text-balance">
                {search.isMaximized ? "Minimize" : "Maximize"}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
          <DateRangeWithShortcuts
            date={date}
            setDate={(newDateRange) => {
              searchParams.delete("time_before");
              searchParams.delete("time_after");
              if (newDateRange?.to) {
                searchParams.set("time_before", newDateRange?.to.toISOString());
              }
              if (newDateRange?.from) {
                searchParams.set(
                  "time_after",
                  newDateRange?.from.toISOString()
                );
              }
              setSearchParams(searchParams, { replace: true });
            }}
            className="min-w-[250px]"
          />

          <MultiSelect
            value={search.request_method as string[]}
            className="w-auto"
            options={REQUEST_METHODS as Writeable<typeof REQUEST_METHODS>}
            onValueChange={(newVal) => {
              searchParams.delete("request_method");
              for (const value of newVal) {
                searchParams.append("request_method", value);
              }
              setSearchParams(searchParams, { replace: true });
            }}
            label="method"
          />

          {extraFilters}

          {selectedFields.includes("status") && (
            <FilterField onRemove={() => removeField("status")}>
              <StatusFilter statuses={search.status ?? []} />
            </FilterField>
          )}

          {selectedFields.includes("request_host") && (
            <FilterField onRemove={() => removeField("request_host")}>
              <FieldValuesFilter
                field="request_host"
                label="host"
                values={search.request_host ?? []}
                fieldValuesQuery={fieldValuesQuery}
              />
            </FilterField>
          )}

          {selectedFields.includes("request_path") && (
            <FilterField onRemove={() => removeField("request_path")}>
              <FieldValuesFilter
                field="request_path"
                label="path"
                values={search.request_path ?? []}
                fieldValuesQuery={fieldValuesQuery}
              />
            </FilterField>
          )}

          {selectedFields.includes("request_query") && (
            <FilterField onRemove={() => removeField("request_query")}>
              <Input
                placeholder="query"
                name="request_query"
                className="max-w-40"
                defaultValue={search.request_query}
                onChange={(ev) => {
                  const newQuery = ev.currentTarget.value;
                  if (newQuery !== (search.request_query ?? "")) {
                    searchForQuery(
                      newQuery.startsWith("?")
                        ? newQuery.substring(1)
                        : newQuery
                    );
                  }
                }}
              />
            </FilterField>
          )}

          {selectedFields.includes("request_ip") && (
            <FilterField onRemove={() => removeField("request_ip")}>
              <FieldValuesFilter
                field="request_ip"
                label="client ip"
                values={search.request_ip ?? []}
                fieldValuesQuery={fieldValuesQuery}
              />
            </FilterField>
          )}

          {selectedFields.includes("request_country_code") && (
            <FilterField onRemove={() => removeField("request_country_code")}>
              <CountryCodeFilter
                countryCodes={search.request_country_code ?? []}
              />
            </FilterField>
          )}

          {selectedFields.includes("request_user_agent") && (
            <FilterField onRemove={() => removeField("request_user_agent")}>
              <FieldValuesFilter
                field="request_user_agent"
                label="user agent"
                values={search.request_user_agent ?? []}
                fieldValuesQuery={fieldValuesQuery}
              />
            </FilterField>
          )}

          {available_fields.length > 0 && (
            <MultiSelect
              value={[]}
              align="start"
              className="w-auto"
              Icon={PlusIcon}
              options={Object.keys(FIELD_LABEL_MAP).filter((label) =>
                available_fields.includes(
                  FIELD_LABEL_MAP[label as keyof typeof FIELD_LABEL_MAP]
                )
              )}
              closeOnSelect
              onValueChange={([newField]) => {
                const field =
                  FIELD_LABEL_MAP[newField as keyof typeof FIELD_LABEL_MAP];
                if (!selectedFields.includes(field)) {
                  flushSync(() => {
                    setSelectedFields([...selectedFields, field]);
                  });

                  const element = parentRef.current?.querySelector(
                    `[name=${field}]`
                  ) as HTMLElement | null;
                  element?.focus();
                }
              }}
              label="Add Filter"
            />
          )}

          {!isEmptySearchParams && (
            <Button
              variant="outline"
              className="inline-flex w-min gap-1"
              onClick={clearFilters}
            >
              <XIcon size={15} />
              <span>Reset filters</span>
            </Button>
          )}
        </div>
      </section>
      <hr className="border-border" />
    </>
  );
}

type FilterFieldProps = {
  children: React.ReactNode;
  onRemove: () => void;
};

function FilterField({ children, onRemove }: FilterFieldProps) {
  return (
    <div className="inline-flex items-center gap-1">
      {children}
      <Button
        onClick={onRemove}
        variant="outline"
        className="bg-inherit"
        type="button"
      >
        <XIcon size={15} className="flex-none" />
        <span className="sr-only">Remove field</span>
      </Button>
    </div>
  );
}

type StatusFilterProps = {
  statuses: string[];
};

function StatusFilter({ statuses }: StatusFilterProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  return (
    <MultiSelect
      value={statuses}
      className="w-auto"
      name="status"
      options={[...new Set(["1xx", "2xx", "3xx", "4xx", "5xx", ...statuses])]}
      closeOnSelect
      onValueChange={(statuses) => {
        searchParams.delete("status");
        statuses.forEach((status) => searchParams.append("status", status));
        setSearchParams(searchParams, { replace: true });
      }}
      label="status"
      acceptArbitraryValues
    />
  );
}

type FieldValuesFilterProps = {
  field: Extract<
    HttpLogFilterField,
    "request_host" | "request_path" | "request_ip" | "request_user_agent"
  >;
  label: string;
  values: string[];
  fieldValuesQuery: HttpLogfieldValuesQuery;
};

/**
 * Filter for the fields whose values are autocompleted by the API.
 */
function FieldValuesFilter({
  field,
  label,
  values,
  fieldValuesQuery
}: FieldValuesFilterProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [inputValue, setInputValue] = React.useState("");

  const { data: valueList = [] } = useQuery(
    fieldValuesQuery({ field, value: inputValue })
  );

  return (
    <MultiSelect
      value={values}
      className="w-auto"
      name={field}
      options={[...new Set([...valueList, ...values])]}
      closeOnSelect
      inputValue={inputValue}
      onInputValueChange={setInputValue}
      onValueChange={(newValues) => {
        searchParams.delete(field);
        newValues.forEach((value) => searchParams.append(field, value));
        setSearchParams(searchParams, { replace: true });
      }}
      label={label}
      acceptArbitraryValues
    />
  );
}

const COUNTRY_CODE_OPTIONS: MultiSelectOption[] = Object.entries(
  COUNTRY_CODE_LIST
).map(([iso, country]) => ({
  value: iso,
  label: (
    <span className="inline-flex items-start gap-1">
      <span className="text-base">{country.flag}</span>
      <span>{country.name}</span>
    </span>
  )
}));

type CountryCodeFilterProps = {
  countryCodes: string[];
};

function CountryCodeFilter({ countryCodes }: CountryCodeFilterProps) {
  const [searchParams, setSearchParams] = useSearchParams();

  return (
    <MultiSelect
      value={countryCodes}
      className="w-auto"
      name="request_country_code"
      options={COUNTRY_CODE_OPTIONS}
      closeOnSelect
      autoFilter
      keepValuesCase
      // Sort by selected values first
      sortOptions={(optionA, optionB) => {
        const valueA = getMultiSelectOptionValue(optionA);
        const valueB = getMultiSelectOptionValue(optionB);
        const isSelectedA = countryCodes.includes(valueA);
        const isSelectedB = countryCodes.includes(valueB);
        if (isSelectedA || isSelectedB) {
          return Number(isSelectedB) - Number(isSelectedA);
        }

        return valueA.localeCompare(valueB, undefined, {
          numeric: true,
          sensitivity: "base"
        });
      }}
      onValueChange={(newCountryCodes) => {
        searchParams.delete("request_country_code");
        newCountryCodes.forEach((countryCode) =>
          searchParams.append("request_country_code", countryCode)
        );
        setSearchParams(searchParams, { replace: true });
      }}
      label="country"
    />
  );
}
