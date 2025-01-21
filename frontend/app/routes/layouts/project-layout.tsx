import { useQuery } from "@tanstack/react-query";
import {
  ContainerIcon,
  LoaderIcon,
  PlusIcon,
  Search,
  SettingsIcon
} from "lucide-react";
import * as React from "react";
import {
  Link,
  Outlet,
  isRouteErrorResponse,
  useLocation,
  useNavigate,
  useRouteError,
  useSearchParams
} from "react-router";
import { useSpinDelay } from "spin-delay";
import { useDebouncedCallback } from "use-debounce";
import { NavLink } from "~/components/nav-link";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from "~/components/ui/breadcrumb";
import { Button } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "~/components/ui/tabs";
import { SPIN_DELAY_DEFAULT_OPTIONS } from "~/lib/constants";
import { projectQueries } from "~/lib/queries";
import type { ValueOf } from "~/lib/types";
import { cn, isNotFoundError } from "~/lib/utils";
import { queryClient } from "~/root";
import { metaTitle } from "~/utils";
import { type Route } from "./+types/project-layout";

export function meta({ error }: Route.MetaArgs) {
  const title = !error
    ? `Project Detail`
    : isNotFoundError(error)
      ? "Error 404 - Project does not exist"
      : "Oops";
  return [metaTitle(title)] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({
  request,
  params
}: Route.ClientLoaderArgs) {
  const searchParams = new URL(request.url).searchParams;

  const queryString = searchParams.get("query") ?? "";

  let project = queryClient.getQueryData(
    projectQueries.single(params.projectSlug).queryKey
  );

  if (!project) {
    // fetch the data on first load to prevent showing the loading fallback
    [project] = await Promise.all([
      queryClient.ensureQueryData(projectQueries.single(params.projectSlug)),
      queryClient.ensureQueryData(
        projectQueries.serviceList(params.projectSlug, {
          query: queryString
        })
      )
    ]);
  }

  return { project };
}

const TABS = {
  SERVICES: "services",
  SETTINGS: "settings"
} as const;

export default function ProjectDetail({
  params,
  loaderData
}: Route.ComponentProps) {
  const { projectSlug: slug } = params;

  const { data: project } = useQuery({
    ...projectQueries.single(params.projectSlug),
    initialData: loaderData.project
  });
  const [searchParams, setSearchParams] = useSearchParams();
  const query = searchParams.get("query") ?? "";

  const projectServiceListQuery = useQuery(
    projectQueries.serviceList(slug, {
      query
    })
  );

  const filterServices = useDebouncedCallback((query: string) => {
    searchParams.set("query", query);
    setSearchParams(searchParams, { replace: true });
  }, 300);

  const isFetchingServices = useSpinDelay(
    projectServiceListQuery.isFetching,
    SPIN_DELAY_DEFAULT_OPTIONS
  );

  const inputRef = React.useRef<React.ComponentRef<"input">>(null);

  const location = useLocation();
  let currentSelectedTab: ValueOf<typeof TABS> = TABS.SERVICES;
  if (location.pathname.match(/settings\/?$/)) {
    currentSelectedTab = TABS.SETTINGS;
  }

  React.useEffect(() => {
    if (inputRef.current && inputRef.current.value !== query) {
      inputRef.current.value = query;
    }
  }, [query]);

  return (
    <main>
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
            <BreadcrumbPage>{slug}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <>
        <section
          id="header"
          className="flex items-center md:flex-nowrap lg:my-0 md:my-1 my-5 flex-wrap  gap-3 justify-between "
        >
          <div className="flex items-center gap-4">
            <h1 className="text-3xl font-medium">{project.slug}</h1>

            <Button asChild variant="secondary" className="flex gap-2">
              <Link to="create-service" prefetch="intent">
                New Service <PlusIcon size={18} />
              </Link>
            </Button>
          </div>
          <div className="flex my-3 flex-wrap w-full md:w-auto  justify-end items-center md:gap-3 gap-1">
            <div
              className={cn(
                "flex lg:my-5 md:my-4 w-full items-center",
                currentSelectedTab !== TABS.SERVICES && "py-6.5"
              )}
            >
              {currentSelectedTab === TABS.SERVICES && (
                <>
                  {isFetchingServices ? (
                    <LoaderIcon
                      size={20}
                      className="animate-spin relative left-4"
                    />
                  ) : (
                    <Search size={20} className="relative left-4" />
                  )}

                  <Input
                    onChange={(e) => filterServices(e.currentTarget.value)}
                    defaultValue={query}
                    className="pl-14 pr-5 -mx-5 w-full my-1 text-sm focus-visible:right-0"
                    placeholder="Ex: ZaneOps"
                    ref={inputRef}
                  />
                </>
              )}
            </div>
          </div>
        </section>

        <nav>
          <ul
            className={cn(
              "overflow-x-auto overflow-y-clip h-[2.55rem] w-full items-start justify-start rounded-none border-b border-border ",
              "inline-flex items-stretch p-0.5 text-muted-foreground"
            )}
          >
            <li>
              <NavLink to=".">
                <span>Services</span>
                <ContainerIcon size={15} className="flex-none" />
              </NavLink>
            </li>

            <li>
              <NavLink to="./settings">
                <span>Settings</span>
                <SettingsIcon size={15} className="flex-none" />
              </NavLink>
            </li>
          </ul>
        </nav>
        <section className="mt-2">
          <Outlet />
        </section>
      </>
    </main>
  );
}

export function ErrorBoundary() {
  const error = useRouteError();

  // when true, this is what used to go to `CatchBoundary`
  if (isRouteErrorResponse(error) && error.status === 404) {
    return (
      <section className="col-span-full ">
        <div className="flex flex-col gap-5 h-[70vh] items-center justify-center">
          <div className="flex-col flex gap-3 items-center">
            <h1 className="text-3xl font-bold">Error 404</h1>
            <p className="text-lg">This project does not exist</p>
          </div>
          <Link to="/">
            <Button>Go home</Button>
          </Link>
        </div>
      </section>
    );
  }

  throw error;
}
