import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  ChevronRightIcon,
  GithubIcon,
  InfoIcon,
  LoaderIcon,
  LockIcon
} from "lucide-react";
import * as React from "react";
import { Form, Link, href, useNavigation } from "react-router";
import { useDebounce } from "use-debounce";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Badge } from "~/components/ui/badge";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from "~/components/ui/breadcrumb";
import { SubmitButton } from "~/components/ui/button";
import {
  Command,
  CommandInput,
  CommandItem,
  CommandList
} from "~/components/ui/command";
import {
  FieldSet,
  FieldSetCheckbox,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
import { Label } from "~/components/ui/label";
import { RadioGroup, RadioGroupItem } from "~/components/ui/radio-group";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { BUILDER_DESCRIPTION_MAP } from "~/lib/constants";
import {
  type GitApp,
  type GitRepository,
  type ServiceBuilder,
  gitAppsQueries
} from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import { queryClient } from "~/root";
import { metaTitle } from "~/utils";
import type { Route } from "./+types/create-git-service-from-gitapp";

export function meta() {
  return [
    metaTitle("New Private Git Service")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const gitApp = await queryClient.ensureQueryData(
    gitAppsQueries.single(params.gitAppId)
  );
  return { gitApp };
}

export default function CreateGitServiceFromGitHubPage({
  params,
  loaderData,
  actionData
}: Route.ComponentProps) {
  const [currentStep, setCurrentStep] = React.useState<
    "FORM" | "CREATED" | "DEPLOYED"
  >("FORM");
  const [serviceSlug, setServiceSlug] = React.useState("");
  const [deploymentHash, setDeploymentHash] = React.useState("");

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
                params.envSlug !== "production"
                  ? "text-link"
                  : "text-green-500 dark:text-primary"
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
            <BreadcrumbLink asChild>
              <Link
                to={href(
                  "/project/:projectSlug/:envSlug/create-service",
                  params
                )}
                prefetch="intent"
              >
                Create service
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>

          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link
                to={href(
                  "/project/:projectSlug/:envSlug/create-service/git-private",
                  params
                )}
                prefetch="intent"
              >
                Git private
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>From github app</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      {currentStep === "FORM" && (
        <StepServiceForm
          actionData={actionData}
          gitApp={loaderData.gitApp}
          onSuccess={(slug) => {
            setCurrentStep("CREATED");
            setServiceSlug(slug);
          }}
        />
      )}
    </>
  );
}

type StepServiceFormProps = {
  gitApp: GitApp;
  onSuccess: (slug: string) => void;
  actionData?: Route.ComponentProps["actionData"];
};

function StepServiceForm({
  onSuccess,
  actionData,
  gitApp
}: StepServiceFormProps) {
  const errors = getFormErrorsFromResponseData(undefined); // TODO

  const formRef = React.useRef<React.ComponentRef<"form">>(null);

  const navigation = useNavigation();
  const isPending = navigation.state === "submitting";

  // if (actionData?.serviceSlug) {
  //   onSuccess(actionData.serviceSlug);
  // }

  const [serviceBuilder, setServiceBuilder] =
    React.useState<ServiceBuilder>("NIXPACKS");

  const [isSpaChecked, setIsSpaChecked] = React.useState(false);
  const [isStaticChecked, setIsStaticChecked] = React.useState(false);

  React.useEffect(() => {
    const key = Object.keys(errors ?? {})[0];
    const field = formRef.current?.elements.namedItem(key) as HTMLInputElement;
    field?.focus();
  }, [errors]);
  const [selectedRepository, setSelectedRepository] =
    React.useState<GitRepository | null>(null);

  return (
    <Form
      ref={formRef}
      method="post"
      className="flex my-10 grow justify-center items-center"
    >
      <div className="card flex lg:w-[35%] md:w-[50%] w-full flex-col gap-3">
        <div className="flex flex-col sm:flex-row items-start gap-1">
          <h1 className="text-3xl font-bold ">New Git Service</h1>
          <Badge
            variant="outline"
            className="text-grey flex items-center gap-1"
          >
            <LockIcon size={15} className="flex-none" />
            <span className="relative">private</span>
          </Badge>
        </div>

        {errors.non_field_errors && (
          <Alert variant="destructive">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{errors.non_field_errors}</AlertDescription>
          </Alert>
        )}

        <FieldSet
          name="slug"
          required
          className="my-2 flex flex-col gap-1"
          errors={errors.slug}
        >
          <FieldSetLabel className="dark:text-card-foreground">
            Slug
          </FieldSetLabel>

          <FieldSetInput
            className="p-3"
            placeholder="ex: zaneops-web-app"
            autoFocus
          />
        </FieldSet>

        <h2 className="text-lg text-grey mt-2">Source</h2>

        <FieldSet
          required
          className="flex flex-col gap-1"
          name="repository_url"
          errors={errors.repository_url}
        >
          <FieldSetLabel className="dark:text-card-foreground">
            Repository
          </FieldSetLabel>

          <FieldSetInput type="hidden" value={selectedRepository?.url} />
          {gitApp.github && (
            <GithubRepositoryList
              githubAppId={gitApp.github.id}
              selectedRepository={selectedRepository}
              onSelect={setSelectedRepository}
              hasError={!!errors.repository_url}
            />
          )}
        </FieldSet>
        <FieldSet
          name="branch_name"
          className="flex flex-col gap-1.5 flex-1"
          required
          errors={errors.branch_name}
        >
          <FieldSetLabel className="dark:text-card-foreground">
            Branch name
          </FieldSetLabel>
          <FieldSetInput placeholder="ex: master" defaultValue="main" />
        </FieldSet>

        <h2 className="text-lg text-grey mt-4">Builder</h2>

        <input type="hidden" name="builder" value={serviceBuilder} />

        <Accordion type="single" collapsible>
          <AccordionItem value={`builder`} className="border-none">
            <AccordionTrigger
              className={cn(
                "w-full px-3 bg-muted rounded-md gap-2 flex items-center justify-between text-start",
                "data-[state=open]:rounded-b-none [&[data-state=open]_svg]:rotate-90 pr-4"
              )}
            >
              <div className="flex flex-col gap-2 items-start">
                <div className="inline-flex gap-2 items-center flex-wrap">
                  <p>
                    {BUILDER_DESCRIPTION_MAP[serviceBuilder].title}
                    {serviceBuilder === "RAILPACK" && (
                      <sup className="text-link">bêta</sup>
                    )}
                  </p>
                </div>

                <small className="inline-flex gap-2 items-center">
                  <span className="text-grey">
                    {BUILDER_DESCRIPTION_MAP[serviceBuilder].description}
                  </span>
                </small>
              </div>

              <ChevronRightIcon size={20} className="text-grey" />
            </AccordionTrigger>
            <AccordionContent className="border-border border-x border-b rounded-b-md p-4 mb-4">
              <RadioGroup
                value={serviceBuilder}
                onValueChange={(value) =>
                  setServiceBuilder(value as ServiceBuilder)
                }
              >
                <div className="flex items-center space-x-2">
                  <RadioGroupItem
                    value="NIXPACKS"
                    id="nixpacks-builder"
                    className="peer"
                  />
                  <Label
                    htmlFor="nixpacks-builder"
                    className="peer-disabled:text-grey"
                  >
                    <span>{BUILDER_DESCRIPTION_MAP["NIXPACKS"].title}</span>
                  </Label>
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} className="text-grey" />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64 dark:bg-card">
                        {BUILDER_DESCRIPTION_MAP["NIXPACKS"].description}
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem
                    value="RAILPACK"
                    id="railback-builder"
                    className="peer"
                  />
                  <Label
                    htmlFor="railback-builder"
                    className="peer-disabled:text-grey"
                  >
                    <span>{BUILDER_DESCRIPTION_MAP["RAILPACK"].title}</span>
                    <sup className="text-link text-sm">bêta</sup>
                  </Label>
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} className="text-grey" />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64 dark:bg-card">
                        {BUILDER_DESCRIPTION_MAP["RAILPACK"].description}
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="DOCKERFILE" id="dockerfile-builder" />
                  <Label htmlFor="dockerfile-builder">
                    {BUILDER_DESCRIPTION_MAP["DOCKERFILE"].title}
                  </Label>
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} className="text-grey" />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64 dark:bg-card">
                        {BUILDER_DESCRIPTION_MAP["DOCKERFILE"].description}
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>

                <div className="flex items-center space-x-2">
                  <RadioGroupItem
                    value="STATIC_DIR"
                    id="static-builder"
                    className="peer"
                  />
                  <Label
                    htmlFor="static-builder"
                    className="peer-disabled:text-grey inline-flex gap-1 items-center"
                  >
                    <span>{BUILDER_DESCRIPTION_MAP["STATIC_DIR"].title}</span>
                  </Label>
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} className="text-grey" />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64 dark:bg-card">
                        {BUILDER_DESCRIPTION_MAP["STATIC_DIR"].description}
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
              </RadioGroup>
            </AccordionContent>
          </AccordionItem>
        </Accordion>

        {serviceBuilder === "NIXPACKS" && (
          <>
            <FieldSet
              name="build_directory"
              className="flex flex-col gap-1.5 flex-1"
              required
              errors={errors.build_directory}
            >
              <FieldSetLabel className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Build directory&nbsp;
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger>
                      <InfoIcon size={15} />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-64">
                      Specify the directory to build. Relative to the root the
                      repository
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </FieldSetLabel>
              <div className="relative">
                <FieldSetInput placeholder="ex: ./apps/web" defaultValue="./" />
              </div>
            </FieldSet>
            {!isStaticChecked && (
              <FieldSet
                name="exposed_port"
                className="flex flex-col gap-1.5 flex-1"
                required
                errors={errors.exposed_port}
              >
                <FieldSetLabel className="dark:text-card-foreground inline-flex items-center gap-0.5">
                  Exposed port&nbsp;
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64">
                        The port your app listens to
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </FieldSetLabel>
                <div className="relative">
                  <FieldSetInput placeholder="ex: 8000" defaultValue="3000" />
                </div>
              </FieldSet>
            )}

            <FieldSet
              name="is_static"
              errors={errors.is_static}
              className="flex-1 inline-flex gap-2 flex-col"
            >
              <div className="inline-flex gap-2 items-center">
                <FieldSetCheckbox
                  checked={isStaticChecked}
                  onCheckedChange={(state) =>
                    setIsStaticChecked(Boolean(state))
                  }
                />

                <FieldSetLabel className="inline-flex gap-1 items-center">
                  Is this a static website ?&nbsp;
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64">
                        If your application is a static site or the final build
                        assets should be served as a static site, enable this.
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </FieldSetLabel>
              </div>
            </FieldSet>
            {isStaticChecked && (
              <>
                <FieldSet
                  name="is_spa"
                  errors={errors.is_spa}
                  className="flex-1 inline-flex gap-2 flex-col"
                >
                  <div className="inline-flex gap-2 items-center">
                    <FieldSetCheckbox
                      checked={isSpaChecked}
                      onCheckedChange={(state) =>
                        setIsSpaChecked(Boolean(state))
                      }
                    />

                    <FieldSetLabel className="inline-flex gap-1 items-center">
                      Is this a Single Page Application (SPA) ?
                    </FieldSetLabel>
                  </div>
                </FieldSet>
                <FieldSet
                  name="publish_directory"
                  className="flex flex-col gap-1.5 flex-1"
                  required
                  errors={errors.publish_directory}
                >
                  <FieldSetLabel className="inline-flex items-center gap-0.5">
                    Publish directory&nbsp;
                    <TooltipProvider>
                      <Tooltip delayDuration={0}>
                        <TooltipTrigger>
                          <InfoIcon size={15} />
                        </TooltipTrigger>
                        <TooltipContent className="max-w-64">
                          If there is a build process involved, please specify
                          the publish directory for the build assets.
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </FieldSetLabel>
                  <div className="relative">
                    <FieldSetInput
                      placeholder="ex: ./public"
                      defaultValue="./dist"
                      className={cn(
                        "disabled:bg-secondary/60",
                        "dark:disabled:bg-secondary-foreground",
                        "disabled:border-transparent disabled:opacity-100"
                      )}
                    />
                  </div>
                </FieldSet>
              </>
            )}
          </>
        )}

        {serviceBuilder === "RAILPACK" && (
          <>
            <FieldSet
              name="build_directory"
              className="flex flex-col gap-1.5 flex-1"
              required
              errors={errors.build_directory}
            >
              <FieldSetLabel className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Build directory&nbsp;
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger>
                      <InfoIcon size={15} />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-64">
                      Specify the directory to build. Relative to the root the
                      repository
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </FieldSetLabel>
              <div className="relative">
                <FieldSetInput placeholder="ex: ./apps/web" defaultValue="./" />
              </div>
            </FieldSet>
            {!isStaticChecked && (
              <FieldSet
                name="exposed_port"
                className="flex flex-col gap-1.5 flex-1"
                required
                errors={errors.exposed_port}
              >
                <FieldSetLabel className="dark:text-card-foreground inline-flex items-center gap-0.5">
                  Exposed port&nbsp;
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64">
                        The port your app listens to
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </FieldSetLabel>
                <div className="relative">
                  <FieldSetInput placeholder="ex: 8000" defaultValue="3000" />
                </div>
              </FieldSet>
            )}

            <FieldSet
              name="is_static"
              errors={errors.is_static}
              className="flex-1 inline-flex gap-2 flex-col"
            >
              <div className="inline-flex gap-2 items-center">
                <FieldSetCheckbox
                  checked={isStaticChecked}
                  onCheckedChange={(state) =>
                    setIsStaticChecked(Boolean(state))
                  }
                />

                <FieldSetLabel className="inline-flex gap-1 items-center">
                  Is this a static website ?&nbsp;
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64">
                        If your application is a static site or the final build
                        assets should be served as a static site, enable this.
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </FieldSetLabel>
              </div>
            </FieldSet>
            {isStaticChecked && (
              <>
                <FieldSet
                  name="is_spa"
                  errors={errors.is_spa}
                  className="flex-1 inline-flex gap-2 flex-col"
                >
                  <div className="inline-flex gap-2 items-center">
                    <FieldSetCheckbox
                      checked={isSpaChecked}
                      onCheckedChange={(state) =>
                        setIsSpaChecked(Boolean(state))
                      }
                    />

                    <FieldSetLabel className="inline-flex gap-1 items-center">
                      Is this a Single Page Application (SPA) ?
                    </FieldSetLabel>
                  </div>
                </FieldSet>
                <FieldSet
                  name="publish_directory"
                  className="flex flex-col gap-1.5 flex-1"
                  required
                  errors={errors.publish_directory}
                >
                  <FieldSetLabel className="inline-flex items-center gap-0.5">
                    Publish directory&nbsp;
                    <TooltipProvider>
                      <Tooltip delayDuration={0}>
                        <TooltipTrigger>
                          <InfoIcon size={15} />
                        </TooltipTrigger>
                        <TooltipContent className="max-w-64">
                          If there is a build process involved, please specify
                          the publish directory for the build assets.
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </FieldSetLabel>
                  <div className="relative">
                    <FieldSetInput
                      placeholder="ex: ./public"
                      defaultValue="./dist"
                      className={cn(
                        "disabled:bg-secondary/60",
                        "dark:disabled:bg-secondary-foreground",
                        "disabled:border-transparent disabled:opacity-100"
                      )}
                    />
                  </div>
                </FieldSet>
              </>
            )}
          </>
        )}

        {serviceBuilder === "DOCKERFILE" && (
          <>
            <FieldSet
              name="build_context_dir"
              className="flex flex-col gap-1.5 flex-1"
              required
              errors={errors.build_context_dir}
            >
              <FieldSetLabel className="dark:text-card-foreground inline-flex items-center gap-0.5">
                Build context directory&nbsp;
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger>
                      <InfoIcon size={15} />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-64">
                      Specify the directory to build relative to the root the
                      repository
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </FieldSetLabel>
              <div className="relative">
                <FieldSetInput placeholder="ex: ./apps/web" defaultValue="./" />
              </div>
            </FieldSet>

            <FieldSet
              className="flex flex-col gap-1.5 flex-1"
              required
              name="dockerfile_path"
              errors={errors.dockerfile_path}
            >
              <FieldSetLabel className="dark:text-card-foreground  inline-flex items-center gap-0.5">
                Dockerfile location&nbsp;
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger>
                      <InfoIcon size={15} />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-64">
                      Relative to the root of the repository
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </FieldSetLabel>
              <div className="relative">
                <FieldSetInput
                  placeholder="ex: ./apps/web/Dockerfile"
                  defaultValue="./Dockerfile"
                />
              </div>
            </FieldSet>
          </>
        )}
        {serviceBuilder === "STATIC_DIR" && (
          <>
            <FieldSet
              name="publish_directory"
              className="flex flex-col gap-1.5 flex-1"
              required
              errors={errors.publish_directory}
            >
              <FieldSetLabel className=" inline-flex items-center gap-0.5">
                Publish directory
              </FieldSetLabel>
              <div className="relative">
                <FieldSetInput
                  placeholder="ex: ./public"
                  defaultValue="./"
                  className={cn(
                    "disabled:bg-secondary/60",
                    "dark:disabled:bg-secondary-foreground",
                    "disabled:border-transparent disabled:opacity-100"
                  )}
                />
              </div>
            </FieldSet>
            {!isSpaChecked && (
              <FieldSet
                name="not_found_page"
                className="flex flex-col gap-1.5 flex-1"
                errors={errors.not_found_page}
              >
                <FieldSetLabel className=" inline-flex items-center gap-0.5">
                  Not found page &nbsp;
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64">
                        Specify a custom file for 404 errors
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </FieldSetLabel>
                <div className="relative">
                  <FieldSetInput
                    placeholder="ex: ./404.html"
                    className={cn(
                      "disabled:bg-secondary/60",
                      "dark:disabled:bg-secondary-foreground",
                      "disabled:border-transparent disabled:opacity-100"
                    )}
                  />
                </div>
              </FieldSet>
            )}
            <FieldSet
              name="is_spa"
              errors={errors.is_spa}
              className="flex-1 inline-flex gap-2 flex-col"
            >
              <div className="inline-flex gap-2 items-center">
                <FieldSetCheckbox
                  checked={isSpaChecked}
                  onCheckedChange={(state) => setIsSpaChecked(Boolean(state))}
                />

                <FieldSetLabel className="inline-flex gap-1 items-center">
                  Is this a Single Page Application (SPA) ?
                </FieldSetLabel>
              </div>
            </FieldSet>

            {isSpaChecked && (
              <FieldSet
                name="index_page"
                className="flex flex-col gap-1.5 flex-1"
                errors={errors.index_page}
                required
              >
                <FieldSetLabel className=" inline-flex items-center gap-0.5">
                  Index page&nbsp;
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-64">
                        Specify a page to redirect all requests to
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </FieldSetLabel>
                <div className="relative">
                  <FieldSetInput
                    placeholder="ex: ./index.html"
                    defaultValue="./index.html"
                    className={cn(
                      "disabled:bg-secondary/60",
                      "dark:disabled:bg-secondary-foreground",
                      "disabled:border-transparent disabled:opacity-100"
                    )}
                  />
                </div>
              </FieldSet>
            )}
          </>
        )}
        <SubmitButton
          className="p-3 rounded-lg gap-2"
          isPending={isPending}
          name="step"
          value="create-service"
        >
          {isPending ? (
            <>
              <span>Creating Service...</span>
              <LoaderIcon className="animate-spin" size={15} />
            </>
          ) : (
            " Create New Service"
          )}
        </SubmitButton>
      </div>
    </Form>
  );
}

type GithubRepositoryListProps = {
  githubAppId: string;
  selectedRepository: GitRepository | null;
  onSelect: (repository: GitRepository) => void;
  hasError?: boolean;
};

function GithubRepositoryList({
  githubAppId,
  onSelect,
  hasError,
  selectedRepository
}: GithubRepositoryListProps) {
  const [isComboxOpen, setComboxOpen] = React.useState(false);
  const [repoSearchQuery, setRepoSearchQuery] = React.useState("");
  const [debouncedValue] = useDebounce(repoSearchQuery, 150);

  const repositoriesListQuery = useQuery(
    gitAppsQueries.githubRepositories(githubAppId, {
      query: debouncedValue
    })
  );

  const repositories = repositoriesListQuery.data ?? [];

  return (
    <Command shouldFilter={false} label="Image">
      <CommandInput
        id="image"
        onFocus={() => setComboxOpen(true)}
        onValueChange={(query) => {
          setRepoSearchQuery(query);
          setComboxOpen(true);
        }}
        onBlur={() => {
          setRepoSearchQuery(
            selectedRepository
              ? `${selectedRepository.owner}/${selectedRepository.repo}`
              : ""
          );
          setComboxOpen(false);
        }}
        className="p-3"
        aria-hidden="true"
        value={repoSearchQuery}
        placeholder="ex: zane-ops/zane-ops"
        name="image"
        aria-invalid={hasError}
      />
      <CommandList
        className={cn({
          "hidden!": !isComboxOpen
        })}
      >
        {repositories.map((repo) => {
          const fullPath = `${repo.owner}/${repo.repo}`;
          return (
            <CommandItem
              key={repo.id}
              value={fullPath}
              className="flex items-start gap-2"
              onSelect={(value) => {
                onSelect(repo);
                setRepoSearchQuery(value);
                setComboxOpen(false);
              }}
            >
              <GithubIcon size={15} className="flex-none relative top-1" />
              <div className="flex flex-col gap-1">
                <span>{fullPath}</span>
              </div>
            </CommandItem>
          );
        })}
      </CommandList>
    </Command>
  );
}

export async function clientAction({}: Route.ClientActionArgs) {}
