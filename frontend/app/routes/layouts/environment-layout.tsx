import { useQuery } from "@tanstack/react-query";
import {
  ArrowRightIcon,
  BoxesIcon,
  ChevronDownIcon,
  ContainerIcon,
  KeyRoundIcon,
  LoaderIcon,
  Search,
  SettingsIcon
} from "lucide-react";
import * as React from "react";
import {
  Link,
  Outlet,
  href,
  isRouteErrorResponse,
  useNavigate,
  useRouteError,
  useSearchParams
} from "react-router";
import { useSpinDelay } from "spin-delay";
import { useDebouncedCallback } from "use-debounce";
import { type NavItem, NavLink } from "~/components/nav-link";
import { StatusBadge } from "~/components/status-badge";
import { Button } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import {
  Menubar,
  MenubarContent,
  MenubarContentItem,
  MenubarMenu,
  MenubarTrigger
} from "~/components/ui/menubar";
import { SPIN_DELAY_DEFAULT_OPTIONS } from "~/lib/constants";
import { environmentQueries, projectQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  cn,
  hasMinRole,
  isNotFoundError,
  metaTitle,
  stringToColor
} from "~/lib/utils";
import {
  getCurrentWorkspace,
  useCurrentWorkspace,
  useCurrentWorkspaceMembership
} from "~/lib/workspace-store";
import type { Route } from "./+types/environment-layout";

export function meta({ error, params }: Route.MetaArgs) {
  const title = !error
    ? `${params.projectSlug} › ${params.envSlug}`
    : isNotFoundError(error)
      ? "Error 404 - Environment does not exist"
      : "Oops";
  return [metaTitle(title)] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({
  request,
  params
}: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  const searchParams = new URL(request.url).searchParams;

  const queryString = searchParams.get("query") ?? "";

  let environment = queryClient.getQueryData(
    environmentQueries.single(workspaceId, params.projectSlug, params.envSlug)
      .queryKey
  );

  const project = await queryClient.ensureQueryData(
    projectQueries.single(workspaceId, params.projectSlug)
  );

  if (!environment) {
    // fetch the data on first load to prevent showing the loading fallback
    [environment] = await Promise.all([
      queryClient.ensureQueryData(
        environmentQueries.single(
          workspaceId,
          params.projectSlug,
          params.envSlug
        )
      ),
      queryClient.ensureQueryData(
        environmentQueries.serviceList(
          workspaceId,
          params.projectSlug,
          params.envSlug,
          {
            query: queryString
          }
        )
      )
    ]);
  }

  return { environment, project };
}

export default function EnvironmentLayout({
  params,
  loaderData
}: Route.ComponentProps) {
  const { projectSlug: slug, envSlug } = params;
  const workspaceId = useCurrentWorkspace().id;
  const navigate = useNavigate();

  const { data: project } = useQuery({
    ...projectQueries.single(workspaceId, params.projectSlug),
    initialData: loaderData.project
  });

  const [searchParams, setSearchParams] = useSearchParams();
  const query = searchParams.get("query") ?? "";

  const projectServiceListQuery = useQuery(
    environmentQueries.serviceList(workspaceId, slug, envSlug, {
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

  const projectColor = stringToColor(project.slug);

  const membership = useCurrentWorkspaceMembership();
  const sidebarNavItems: NavItem[] = [
    {
      title: "Services",
      href: ".",
      icon: ContainerIcon
    }
  ];

  if (hasMinRole(membership, "Member")) {
    sidebarNavItems.push({
      title: "Variables",
      href: "variables",
      icon: KeyRoundIcon
    });
  }

  sidebarNavItems.push({
    title: "Settings",
    href: "settings",
    icon: SettingsIcon
  });

  return (
    <section>
      <div className="pt-0">
        <nav>
          <Link
            to={href("/workspace/project/:projectSlug/settings", {
              projectSlug: project.slug
            })}
            className="underline inline-flex gap-0.5 px-0 items-center text-sm"
          >
            <SettingsIcon size={15} className="flex-none" />
            <span>Project settings</span>
            <ArrowRightIcon size={15} className="flex-none" />
          </Link>
        </nav>

        <section
          id="header"
          className="flex items-center md:flex-nowrap lg:my-0 md:my-1 my-5 flex-wrap gap-3 justify-between"
        >
          <div className="flex items-start gap-4">
            <div className={cn("flex gap-2 items-center flex-wrap")}>
              <Link
                to={href("/workspace/project/:projectSlug/:envSlug", {
                  ...params,
                  envSlug: "production"
                })}
                style={
                  {
                    "--color-light": projectColor.light,
                    "--color-dark": projectColor.dark
                  } as React.CSSProperties
                }
                className={cn(
                  "size-12 text-xl flex-none rounded-md flex items-center justify-center",
                  "text-(--color-light) dark:text-(--color-dark)",
                  "bg-(--color-light)/10 dark:bg-(--color-dark)/10",
                  "border  border-(--color-light)/10 dark:border-(--color-dark)/10",
                  "focus-visible:outline-hidden focus-visible:ring-2",
                  "focus-visible:ring-ring focus-visible:ring-offset-2",
                  "ring-offset-background transition-colors"
                )}
              >
                <span>{project.slug.charAt(0).toUpperCase()}</span>
              </Link>
              <div className="flex flex-col gap-0 items-start relative -top-0.5">
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
                  className="text-xs px-2 py-0"
                >
                  {envSlug}
                </StatusBadge>
              </div>
            </div>

            <Menubar className="border-none w-fit">
              <MenubarMenu>
                <MenubarTrigger asChild>
                  <Button variant="secondary" className="flex gap-2 ">
                    New <ChevronDownIcon size={18} />
                  </Button>
                </MenubarTrigger>
                <MenubarContent
                  align="start"
                  alignOffset={-35}
                  sideOffset={5}
                  className="border min-w-0 mx-9  border-border"
                >
                  <MenubarContentItem
                    icon={ContainerIcon}
                    text="Service"
                    onClick={() => {
                      navigate(
                        href(
                          "/workspace/project/:projectSlug/:envSlug/create-service",
                          params
                        )
                      );
                    }}
                  />

                  <MenubarContentItem
                    icon={BoxesIcon}
                    text="Compose Stack"
                    onClick={() => {
                      navigate(
                        href(
                          "/workspace/project/:projectSlug/:envSlug/create-compose-stack",
                          params
                        )
                      );
                    }}
                  />
                </MenubarContent>
              </MenubarMenu>
            </Menubar>
          </div>

          <div className="flex my-0 flex-wrap w-full md:w-auto  justify-end items-center md:gap-3 gap-1">
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
      </div>

      <nav>
        <ul
          className={cn(
            "overflow-x-auto overflow-y-clip h-[2.55rem] w-full items-start justify-start rounded-none border-b border-border ",
            "inline-flex items-stretch p-0.5 text-muted-foreground"
          )}
        >
          {sidebarNavItems.map((item) => (
            <li key={item.title}>
              <NavLink to={item.href}>
                <span>{item.title}</span>
                <item.icon size={15} className="flex-none" />
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <section className="mt-2">
        <Outlet />
      </section>
    </section>
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
          <Link to={href("/")} prefetch="intent">
            <Button>Go home</Button>
          </Link>
        </div>
      </section>
    );
  }

  throw error;
}
