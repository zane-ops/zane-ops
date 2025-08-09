import { useQuery } from "@tanstack/react-query";
import {
  ContainerIcon,
  LoaderIcon,
  NetworkIcon,
  PlusIcon,
  Search,
  SettingsIcon
} from "lucide-react";
import * as React from "react";
import {
  Link,
  Outlet,
  isRouteErrorResponse,
  useNavigate,
  useRouteError,
  useSearchParams
} from "react-router";
import { useSpinDelay } from "spin-delay";
import { useDebouncedCallback } from "use-debounce";
import { NavLink } from "~/components/nav-link";
import { StatusBadge } from "~/components/status-badge";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbSeparator
} from "~/components/ui/breadcrumb";
import { Button } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "~/components/ui/select";
import { SPIN_DELAY_DEFAULT_OPTIONS } from "~/lib/constants";
import { projectQueries } from "~/lib/queries";
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
        projectQueries.serviceList(params.projectSlug, params.envSlug, {
          query: queryString
        })
      )
    ]);
  }

  return { project };
}

export default function ProjectDetail({
  params,
  loaderData
}: Route.ComponentProps) {
  const { projectSlug: slug, envSlug } = params;
  const navigate = useNavigate();

  const { data: project } = useQuery({
    ...projectQueries.single(params.projectSlug),
    initialData: loaderData.project
  });
  const [searchParams, setSearchParams] = useSearchParams();
  const query = searchParams.get("query") ?? "";

  const projectServiceListQuery = useQuery(
    projectQueries.serviceList(slug, envSlug, {
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
            <BreadcrumbLink asChild>
              <Link
                to={`/project/${params.projectSlug}/production`}
                prefetch="intent"
              >
                {slug}
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>

          <BreadcrumbSeparator />

          <BreadcrumbItem>
            <Select
              name="environment"
              onValueChange={(env) => {
                navigate(
                  `/project/${params.projectSlug}/${env}?${searchParams.toString()}`,
                  {
                    replace: true
                  }
                );
              }}
              value={params.envSlug}
            >
              <SelectTrigger
                id="healthcheck_type"
                className={cn(
                  "data-disabled:bg-secondary/60 dark:data-disabled:bg-secondary-foreground",
                  "data-disabled:opacity-100 data-disabled:border-transparent",
                  "text-muted-foreground"
                )}
              >
                <SelectValue placeholder="Select an environment" />
              </SelectTrigger>
              <SelectContent>
                {project.environments.map((env) => (
                  <SelectItem key={env.id} value={env.name}>
                    {env.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <>
        <section
          id="header"
          className="flex items-center md:flex-nowrap lg:my-0 md:my-1 my-5 flex-wrap  gap-3 justify-between "
        >
          <div className="flex items-center gap-4">
            <div className="flex flex-col gap-1 items-start">
              <h1 className="text-3xl font-medium">{project.slug}</h1>
              <StatusBadge
                color={
                  envSlug == "production"
                    ? "green"
                    : envSlug.startsWith("preview")
                      ? "blue"
                      : "gray"
                }
                pingState="hidden"
              >
                {envSlug}
              </StatusBadge>
            </div>

            <Button asChild variant="secondary" className="flex gap-2">
              <Link to="create-service" prefetch="intent">
                New Service <PlusIcon size={18} />
              </Link>
            </Button>
          </div>
          <div className="flex my-3 flex-wrap w-full md:w-auto  justify-end items-center md:gap-3 gap-1">
            <div className={cn("flex lg:my-5 md:my-4 w-full items-center")}>
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
              <NavLink to={`./settings`}>
                <span>Settings</span>
                <SettingsIcon size={15} className="flex-none" />
              </NavLink>
            </li>

            <li>
              <NavLink to={`./environments`}>
                <span>Environments</span>
                <NetworkIcon size={15} className="flex-none" />
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
          <Link to="/" prefetch="intent">
            <Button>Go home</Button>
          </Link>
        </div>
      </section>
    );
  }

  throw error;
}
