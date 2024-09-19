import {
  Link,
  createFileRoute,
  notFound,
  useNavigate
} from "@tanstack/react-router";
import { ChevronsUpDown, PlusIcon, Rocket, Search, Trash } from "lucide-react";
import { useDebounce } from "use-debounce";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import { Loader } from "~/components/loader";
import { MetaTitle } from "~/components/meta-title";
import { DockerServiceCard, GitServiceCard } from "~/components/service-cards";
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
import {
  Menubar,
  MenubarContent,
  MenubarContentItem,
  MenubarMenu,
  MenubarTrigger
} from "~/components/ui/menubar";
import { Separator } from "~/components/ui/separator";
import { projectServiceListSearchSchema } from "~/key-factories";
import { useProjectServiceList } from "~/lib/hooks/use-project-service-list";
import { useProjectSingle } from "~/lib/hooks/use-project-single";
import { timeAgoFormatter } from "~/utils";

export const Route = createFileRoute("/_dashboard/project/$slug")({
  validateSearch: (search) => projectServiceListSearchSchema.parse(search),
  component: withAuthRedirect(ProjectDetail)
});

function ProjectDetail() {
  const { slug } = Route.useParams();
  const { query = "" } = Route.useSearch();
  const [debouncedValue] = useDebounce(query, 300);

  const navigate = useNavigate();

  const projectServiceListQuery = useProjectServiceList(slug, {
    query: debouncedValue
  });
  const projectSingleQuery = useProjectSingle(slug);
  const serviceList = projectServiceListQuery.data?.data;
  const project = projectSingleQuery.data?.data;

  return (
    <main>
      <Breadcrumb>
        <BreadcrumbList className="text-sm">
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/">Projects</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage className="capitalize">{slug}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      {projectSingleQuery.isLoading || projectServiceListQuery.isLoading ? (
        <>
          <div className="col-span-full">
            <Loader className="h-[70vh]" />
          </div>
        </>
      ) : project === undefined ? (
        <>
          <section className="col-span-full ">
            <MetaTitle title="404 - Project does not exist" />
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
        </>
      ) : (
        <>
          <MetaTitle title="Project Detail" />

          <div className="flex items-center md:flex-nowrap lg:my-0 md:my-1 my-5 flex-wrap  gap-3 justify-between ">
            <div className="flex items-center gap-4">
              <h1 className="text-3xl capitalize font-medium">
                {project.slug}
              </h1>

              <Button asChild variant="secondary" className="flex gap-2">
                <Link to="create-service">
                  New Service <PlusIcon size={18} />
                </Link>
              </Button>
            </div>
            <div className="flex my-3 flex-wrap  w-full justify-end items-center md:gap-3 gap-1">
              <div className="flex md:my-5 lg:w-1/3 md:w-1/2 w-full items-center">
                <Search size={20} className="relative left-5" />
                <Input
                  onChange={(e) => {
                    navigate({
                      search: {
                        query: e.target.value
                      },
                      replace: true
                    });
                  }}
                  defaultValue={query}
                  className="px-14 -mx-5 w-full my-1 text-sm focus-visible:right-0"
                  placeholder="Ex: ZaneOps"
                />
              </div>
              <div className="md:w-fit w-full">
                <Menubar className="border border-border md:w-fit w-full">
                  <MenubarMenu>
                    <MenubarTrigger className="flex md:w-fit w-full ring-secondary md:justify-center justify-between text-sm items-center gap-1">
                      Status
                      <ChevronsUpDown className="w-4" />
                    </MenubarTrigger>
                    <MenubarContent className="border w-[calc(var(--radix-menubar-trigger-width)+0.5rem)] border-border md:min-w-6 md:w-auto">
                      <MenubarContentItem icon={Rocket} text="Active" />
                      <MenubarContentItem icon={Trash} text="Archived" />
                    </MenubarContent>
                  </MenubarMenu>
                </Menubar>
              </div>
            </div>
          </div>

          <Separator />
          <div className="py-8  grid lg:grid-cols-3 md:grid-cols-2 grid-cols-1 place-content-center  gap-8">
            {serviceList?.length === 0 && (
              <section className="flex gap-3 h-96 col-span-full flex-col items-center justify-center flex-grow py-20">
                <div className="text-center">
                  {debouncedValue.length > 0 ? (
                    <>
                      <h2 className="text-2xl font-medium">
                        No services match the filter criteria
                      </h2>
                      <h3 className="text-lg text-gray-500">
                        Your search for`{debouncedValue}` did not return any
                        results.
                      </h3>
                    </>
                  ) : (
                    <>
                      <div>
                        <h1 className="text-2xl font-bold">
                          No services found in this project
                        </h1>
                        <h2 className="text-lg">
                          Would you like to start by creating one?
                        </h2>
                      </div>
                      <Button asChild>
                        <Link to={`create-service`}>Create a new service</Link>
                      </Button>
                    </>
                  )}
                </div>
              </section>
            )}

            {serviceList?.map((service) => {
              if (service.type === "docker") {
                return (
                  <DockerServiceCard
                    slug={service.slug}
                    image={service.image}
                    key={service.id}
                    tag={service.tag}
                    volumeNumber={service.volume_number}
                    status={service.status}
                    updatedAt={timeAgoFormatter(service.updated_at)}
                    url={service.url}
                  />
                );
              }

              return (
                <GitServiceCard
                  slug={service.slug}
                  branchName={service.branch}
                  repository={service.repository}
                  status={service.status}
                  key={service.id}
                  updatedAt={timeAgoFormatter(service.updated_at)}
                  lastCommitMessage={service.last_commit_message}
                  url={service.url}
                />
              );
            })}
          </div>
        </>
      )}
    </main>
  );
}
