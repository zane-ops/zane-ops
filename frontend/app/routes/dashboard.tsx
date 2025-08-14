import * as React from "react";
import type { Route } from "./+types/dashboard";

import { ArrowUpDownIcon, LoaderIcon, SearchIcon, XIcon } from "lucide-react";

import { Link, useLoaderData, useSearchParams } from "react-router";
import { Input } from "~/components/ui/input";

import { useQuery } from "@tanstack/react-query";
import { useSpinDelay } from "spin-delay";
import { useDebouncedCallback } from "use-debounce";
import { RecentDeploymentCard } from "~/components/deployment-cards";
import { MultiSelect } from "~/components/multi-select";
import { ProjectCard } from "~/components/project-card";
import { Button } from "~/components/ui/button";
import { SPIN_DELAY_DEFAULT_OPTIONS } from "~/lib/constants";
import {
  deploymentQueries,
  projectQueries,
  projectSearchSchema
} from "~/lib/queries";
import { cn } from "~/lib/utils";
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
  const [projectList, recentDeployments] = await Promise.all([
    queryClient.ensureQueryData(projectQueries.list(filters)),
    queryClient.ensureQueryData(deploymentQueries.recent)
  ]);
  return {
    projectList,
    recentDeployments
  };
}

export default function ProjectList() {
  return (
    <main className="flex flex-col gap-10">
      <h1 className="text-2xl font-medium">Dashboard</h1>
      <ProjectsListSection />
      <RecentDeploymentsSection />
    </main>
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
  const noProjects = projectList.length === 0;
  const emptySearchParams =
    !(searchParams.get("slug")?.trim() ?? "") &&
    !searchParams.get("sort_by") &&
    !searchParams.get("per_page") &&
    !searchParams.get("page");

  const searchProjects = useDebouncedCallback((slug: string) => {
    searchParams.set("slug", slug);
    setSearchParams(searchParams, { replace: true });
  }, 300);

  const isFetchingProjects = useSpinDelay(
    projectActiveQuery.isFetching,
    SPIN_DELAY_DEFAULT_OPTIONS
  );

  const inputRef = React.useRef<React.ComponentRef<"input">>(null);

  React.useEffect(() => {
    if (inputRef.current && inputRef.current.value !== slug) {
      inputRef.current.value = slug;
    }
  }, [slug]);

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
            ref={inputRef}
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
        {!emptySearchParams && (
          <Button variant="outline" className="inline-flex w-min gap-1" asChild>
            <Link to="./" prefetch="intent" replace>
              <XIcon size={15} />
              <span>Reset filters</span>
            </Link>
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
        {emptySearchParams && noProjects && (
          <div
            className={cn(
              "flex flex-col items-center justify-center gap-2 px-6 py-20",
              "border-border rounded-lg w-full border-dashed border-1 text-grey",
              "col-span-full"
            )}
          >
            <h3 className="text-2xl font-medium text-card-foreground">
              Welcome to ZaneOps
            </h3>
            <p>You don't have any project yet</p>
            <Button asChild>
              <Link prefetch="intent" to="/create-project">
                Start by creating one
              </Link>
            </Button>
          </div>
        )}
        {noResults && (
          <div
            className={cn(
              "flex flex-col items-center justify-center gap-2 px-6 py-20",
              "border-border rounded-lg w-full border-dashed border-1 text-grey",
              "col-span-full"
            )}
          >
            <h3 className="text-xl font-medium text-card-foreground">
              No projects match the filter criteria
            </h3>
            <p>
              Your search for <em>`{slug.trim()}`</em> did not return any
              results.
            </p>
          </div>
        )}
        {projectList.map((project) => (
          <ProjectCard project={project} />
        ))}
      </div>
    </section>
  );
}

function RecentDeploymentsSection() {
  const loaderData = useLoaderData<typeof clientLoader>();

  const { data: recentDeployments } = useQuery({
    ...deploymentQueries.recent,
    initialData: loaderData.recentDeployments
  });

  if (recentDeployments.length === 0) return null;

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm text-grey">Recent deployments</h2>
      <div
        style={{
          "--grid-area-xs": `
              "card1"
              "card1"
              "card1"
              "card1"

              "card2"
              "card2"
              "card2"
              "card2"

              "card3"
              "card3"
              "card3"
              "card3"

              "card4"
              "card4"
              "card4"
              "card4"

              "card5"
              "card5"
              "card5"
              "card5"
          `,
          "--grid-area-sm": `
             "card1 card1 card2 card2"
             "card1 card1 card2 card2"
             "card1 card1 card2 card2"
             "card1 card1 card2 card2"

             "card3 card3 card4 card4"
             "card3 card3 card4 card4"
             "card3 card3 card4 card4"
             "card3 card3 card4 card4"

             ". card5 card5 ."
             ". card5 card5 ."
             ". card5 card5 ."
             ". card5 card5 ."
          `,
          "--grid-area-md": `
             "card1 card1 card2 card2 card3 card3"
             "card1 card1 card2 card2 card3 card3"
             "card1 card1 card2 card2 card3 card3"
             "card1 card1 card2 card2 card3 card3"

             ". card4 card4 card5 card5 ."
             ". card4 card4 card5 card5 ."
             ". card4 card4 card5 card5 ."
             ". card4 card4 card5 card5 ."
          `,
          "--grid-area-lg": `
             "card1 card2 card3 card4 card5"
             "card1 card2 card3 card4 card5"
             "card1 card2 card3 card4 card5"
             "card1 card2 card3 card4 card5"
          `
        }}
        className={cn(
          "grid sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-5 gap-4",
          "[grid-template-areas:var(--grid-area-xs)]",
          "md:[grid-template-areas:var(--grid-area-md)]",
          "sm:[grid-template-areas:var(--grid-area-sm)]",
          "lg:[grid-template-areas:var(--grid-area-lg)]"
        )}
      >
        {recentDeployments.map((dpl, index) => (
          <RecentDeploymentCard
            style={{
              gridArea: `card${index + 1}`
            }}
            key={dpl.hash}
            hash={dpl.hash}
            commit_message={dpl.commit_message}
            queued_at={new Date(dpl.queued_at)}
            finished_at={
              dpl.finished_at ? new Date(dpl.finished_at) : undefined
            }
            started_at={dpl.started_at ? new Date(dpl.started_at) : undefined}
            status={dpl.status}
            env_slug={dpl.service.environment.name}
            service_slug={dpl.service.slug}
            project_slug={dpl.service.project.slug}
          />
        ))}
      </div>
    </section>
  );
}
