import type { Route } from "./+types/dashboard";

import { ArrowUpDownIcon, LoaderIcon, SearchIcon } from "lucide-react";

import { useLoaderData, useSearchParams } from "react-router";
import { Input } from "~/components/ui/input";

import { useQuery } from "@tanstack/react-query";
import { useSpinDelay } from "spin-delay";
import { useDebouncedCallback } from "use-debounce";
import { MultiSelect } from "~/components/multi-select";
import { ProjectCard } from "~/components/project-cards";
import { SPIN_DELAY_DEFAULT_OPTIONS } from "~/lib/constants";
import { projectQueries, projectSearchSchema } from "~/lib/queries";
import { queryClient } from "~/root";

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const searchParams = new URL(request.url).searchParams;

  const search = projectSearchSchema.parse(searchParams);
  const { slug = "", sort_by = ["-updated_at"] } = search;
  const filters = {
    slug,
    sort_by
  };

  // fetch the data on first load to prevent showing the loading fallback
  const projectList = await queryClient.ensureQueryData(
    projectQueries.list(filters)
  );

  return {
    projectList
  };
}

export default function ProjectList() {
  return (
    <main className="flex flex-col gap-10">
      <h1 className="text-2xl font-medium">Dashboard</h1>
      <ProjectsListSection />
      {/* <RecentDeploymentsSection /> */}
    </main>
  );
}

function RecentDeploymentsSection() {
  return (
    <section className="flex flex-col gap-3">
      <details className="marker:hidden">
        <summary className="text-sm text-grey">Recent deployments</summary>
        <div className="flex flex-col gap-2 my-2">
          <div className="border-border border-dashed border-1 flex items-center justify-center px-6 py-8 text-grey">
            No Deployments yet
          </div>
        </div>
      </details>
    </section>
  );
}

const sortKeyMap: Record<string, string> = {
  slug: "Alphabetical",
  "-updated_at": "Last Updated"
};

const sortValueMap = {
  Alphabetical: "slug",
  "Last Updated": "-updated_at"
};
function ProjectsListSection() {
  const loaderData = useLoaderData<typeof clientLoader>();

  const [searchParams, setSearchParams] = useSearchParams();
  const search = projectSearchSchema.parse(searchParams);
  const { slug = "", sort_by } = search;

  const filters = {
    slug,

    sort_by
  };

  const projectActiveQuery = useQuery({
    ...projectQueries.list(filters),
    initialData: loaderData.projectList
  });

  const projectList = projectActiveQuery.data;

  const noResults = projectList.length === 0 && slug.trim() !== "";
  const emptySearchParams =
    !(searchParams.get("slug")?.trim() ?? "") &&
    !searchParams.get("sort_by") &&
    !searchParams.get("per_page") &&
    !searchParams.get("page");
  const noProjects = projectList.length === 0;

  const searchProjects = useDebouncedCallback((slug: string) => {
    searchParams.set("slug", slug);
    setSearchParams(searchParams, { replace: true });
  }, 300);

  const isFetchingProjects = useSpinDelay(
    projectActiveQuery.isFetching,
    SPIN_DELAY_DEFAULT_OPTIONS
  );

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm text-grey">
        Your Projects ({projectList.length}
        {slug.trim().length > 0 && " found"})
      </h2>
      <div className="flex flex-wrap items-center md:gap-3 gap-1">
        <div className="flex md:w-[30%] w-full items-center">
          {isFetchingProjects ? (
            <LoaderIcon size={20} className="animate-spin relative left-4" />
          ) : (
            <SearchIcon size={20} className="relative left-4" />
          )}

          <Input
            onChange={(e) => {
              searchProjects(e.currentTarget.value);
            }}
            defaultValue={slug}
            className="px-14 -mx-5 w-full my-1 text-sm focus-visible:right-0"
            placeholder="Ex: ZaneOps"
          />
        </div>

        <MultiSelect
          value={(sort_by ?? []).map((key) => sortKeyMap[key])}
          className="w-auto border-muted"
          options={["Alphabetical", "Last Updated"]}
          Icon={ArrowUpDownIcon}
          label="Sort By"
          order="label-icon"
          onValueChange={(newVal) => {
            searchParams.delete("sort_by");

            for (const value of newVal) {
              // @ts-expect-error
              const field = sortValueMap[value];
              searchParams.append("sort_by", field);
            }
            setSearchParams(searchParams, { replace: true });
          }}
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
        {projectList.map((project) => (
          <ProjectCard project={project} />
        ))}
      </div>
    </section>
  );
}
