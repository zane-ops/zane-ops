import { useQuery } from "@tanstack/react-query";
import { ChevronRightIcon, SearchIcon } from "lucide-react";
import * as React from "react";
import { Link, href, useLoaderData, useSearchParams } from "react-router";
import { MultiSelect } from "~/components/multi-select";
import { Pagination } from "~/components/pagination";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from "~/components/ui/breadcrumb";
import { Card } from "~/components/ui/card";
import { Checkbox } from "~/components/ui/checkbox";
import { Input } from "~/components/ui/input";
import { TEMPLATE_API_HOST } from "~/lib/constants";
import { templateQueries, templateSearchFilters } from "~/lib/queries";
import { cn } from "~/lib/utils";
import { queryClient } from "~/root";
import { metaTitle } from "~/utils";
import type { Route } from "./+types/compose-stack-template-list";

export function meta() {
  return [
    metaTitle("New ZaneOps Template Stack")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const searchParams = new URL(request.url).searchParams;
  const filters = templateSearchFilters.parse(searchParams);

  const [templates, tags] = await Promise.all([
    queryClient.ensureQueryData(templateQueries.search(filters)),
    queryClient.ensureQueryData(templateQueries.tags)
  ]);

  return {
    templates,
    tags
  };
}

export default function ComposeStackTemplateListPage({
  params
}: Route.ComponentProps) {
  return (
    <>
      <Breadcrumb>
        <BreadcrumbList className="text-sm">
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/" prefetch="intent">
                Projects
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link
                to={`/project/${params.projectSlug}/production`}
                prefetch="intent"
              >
                {params.projectSlug}
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>

          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink
              asChild
              className={cn(
                params.envSlug === "production"
                  ? "text-green-500 dark:text-primary"
                  : params.envSlug.startsWith("preview")
                    ? "text-link"
                    : ""
              )}
            >
              <Link
                to={`/project/${params.projectSlug}/${params.envSlug}`}
                prefetch="intent"
              >
                {params.envSlug}
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink>
              <Link
                to={href(
                  "/project/:projectSlug/:envSlug/create-compose-stack",
                  params
                )}
                prefetch="intent"
              >
                Create compose stack
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>From ZaneOps template</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <TemplateSearchList />
    </>
  );
}

function TemplateSearchList() {
  const loaderData = useLoaderData<Route.ComponentProps["loaderData"]>();
  const [searchParams, setSearchParams] = useSearchParams();

  const filters = templateSearchFilters.parse(searchParams);
  const { data: templates } = useQuery({
    ...templateQueries.search(filters),
    initialData: loaderData.templates
  });

  const filterTemplates = (query: string) => {
    searchParams.set("query", query);
    searchParams.set("page", "1");
    setSearchParams(searchParams, { replace: true });
  };

  const [searchQuery, setSearchQuery] = React.useState(filters.query ?? "");

  const hits = templates.hits ?? [];

  let totalPages = 1;

  if (templates.found > hits.length) {
    totalPages = Math.ceil(templates.found / filters.perPage);
  }

  return (
    <div className="flex my-20 flex-col gap-8 max-w-5xl mx-auto">
      <h1 className="text-center text-3xl font-medium">
        Deploy your app in seconds
      </h1>
      <div className="flex flex-col gap-2">
        <form
          action={(formData) => {
            filterTemplates(formData.get("query")?.toString() ?? "");
          }}
          className="flex flex-col md:flex-row items-center gap-2 relative"
        >
          <Input
            placeholder="Search templates... (e.g. postgres, redis, n8n)"
            name="query"
            value={searchQuery}
            onChange={(ev) => {
              const query = ev.currentTarget.value;
              setSearchQuery(query);
              filterTemplates(query);
            }}
            className="grow pr-10"
            autoFocus
            type="search"
          />

          <SearchIcon className="absolute top-1/2 -translate-y-1/2 right-4 size-4 flex-none text-(--sl-color-text)" />
        </form>
        <small className="text-start w-full text-grey">
          Found {templates.found} results in {templates.search_time_ms}ms
        </small>
      </div>

      <div className="grid md:grid-cols-4 lg:grid-cols-5 gap-4 place-items-start">
        <TagsListForm
          selectedTags={filters.tags}
          onTagSelectChange={(newTags) => {
            searchParams.delete("tags");
            for (const tag of newTags) {
              searchParams.append("tags", tag);
            }
            setSearchParams(searchParams, { replace: true });
          }}
        />
        <div className="flex flex-col gap-8 md:col-span-3 lg:col-span-4 items-center w-full">
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {hits.map(({ document }) => (
              <TemplateCard
                key={document.id}
                id={document.id}
                name={document.name}
                description={document.description}
                logoUrl={document.logoUrl}
              />
            ))}
          </div>

          {templates.found > 0 && (
            <Pagination
              totalPages={totalPages}
              currentPage={filters.page}
              perPage={filters.perPage}
              onChangePage={(newPage) => {
                searchParams.set("page", newPage.toString());
                setSearchParams(searchParams, { replace: true });
              }}
              pageSizeOptions={[15, 30, 50, 100]}
              onChangePerPage={(newPerPage) => {
                searchParams.set("perPage", newPerPage.toString());
                searchParams.set("page", "1");
                setSearchParams(searchParams, { replace: true });
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

type TemplateCardProps = {
  id: string;
  name: string;
  description: string;
  logoUrl: string;
};

function TemplateCard({
  id,
  name,
  description,
  logoUrl: logo
}: TemplateCardProps) {
  const logoUrl = new URL(logo, TEMPLATE_API_HOST);

  return (
    <Card
      className={cn(
        "p-4 rounded-md bg-toggle dark:bg-muted relative",
        "ring-1 ring-transparent hover:ring-primary focus-within:ring-primary",
        "transition-colors duration-300  shadow-sm",
        "min-h-38"
      )}
    >
      <div className="flex flex-col items-start gap-4">
        <div className="flex justify-between gap-2 items-center w-full">
          <div className="flex items-center gap-2  border-gray-400/30  w-full">
            <img
              src={logoUrl.toString()}
              alt={name}
              className="size-8 object-contain flex-none rounded-sm"
            />
            <Link
              prefetch="intent"
              to={`./${id}`}
              className="font-medium truncate after:inset-0 after:absolute  no-underline text-card-foreground"
            >
              {name}
            </Link>
          </div>

          <ChevronRightIcon className="size-4 flex-none text-grey" />
        </div>

        <div>
          <p className="text-sm line-clamp-3 text-grey">{description}</p>
        </div>
      </div>
    </Card>
  );
}

type TagsListFormProps = {
  selectedTags: string[];
  onTagSelectChange: (newValues: string[]) => void;
};

function TagsListForm({ selectedTags, onTagSelectChange }: TagsListFormProps) {
  const loaderData = useLoaderData<Route.ComponentProps["loaderData"]>();

  const { data: allTags } = useQuery({
    ...templateQueries.tags,
    initialData: loaderData.tags
  });

  const [tagSearch, setTagSearch] = React.useState("");

  const tagList = React.useMemo(() => {
    const filteredTags = allTags.toSorted((tagA, tagB) => {
      // put selected tags first & sort alphabetically
      if (selectedTags.includes(tagA) && selectedTags.includes(tagB)) {
        return tagA > tagB ? 1 : -1;
      }
      if (selectedTags.includes(tagA)) {
        return -1;
      }
      if (selectedTags.includes(tagB)) {
        return 1;
      }
      return 0;
    });

    return filteredTags.filter((tag) => tag.includes(tagSearch));
  }, [tagSearch, selectedTags, allTags]);

  return (
    <form className="flex flex-col gap-2.5 w-full md:sticky top-24">
      <h3 className="text-lg">Tags</h3>

      <MultiSelect
        options={tagList}
        value={selectedTags}
        onValueChange={onTagSelectChange}
        label="selected"
        align="start"
        popoverClassName="w-full h-80 max-h-80 overflow-auto"
        itemClassName="max-w-[130px]"
        className="md:hidden"
        maxCount={3}
      />

      <Input
        placeholder="search tags"
        className="py-1 hidden md:inline-flex"
        type="search"
        value={tagSearch}
        onChange={(ev) => {
          setTagSearch(ev.currentTarget.value);
        }}
      />

      <ul
        className={cn(
          "hidden md:grid md:grid-cols-1 pl-0 list-none gap-1 shrink",
          "min-h-0 h-80 max-h-80 overflow-auto place-content-start"
        )}
      >
        {tagList.map((tag) => (
          <li key={tag}>
            <label
              className={cn(
                "m-0 w-full cursor-pointer py-1 px-2",
                "flex items-start gap-1.5 rounded-sm group",
                "transition-transform duration-100 active:scale-95"
              )}
            >
              <Checkbox
                checked={selectedTags.includes(tag)}
                onCheckedChange={(checked) => {
                  if (checked) {
                    onTagSelectChange([...selectedTags, tag]);
                  } else {
                    onTagSelectChange(selectedTags.filter((t) => t !== tag));
                  }
                }}
                className="relative top-1 border-grey/40"
              />
              <span
                className={cn(
                  "text-grey",
                  selectedTags.includes(tag) && "text-card-foreground"
                )}
              >
                {tag}
              </span>
            </label>
          </li>
        ))}
      </ul>
    </form>
  );
}
