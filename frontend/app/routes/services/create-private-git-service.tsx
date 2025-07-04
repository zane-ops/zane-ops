import { LockIcon } from "lucide-react";
import * as React from "react";
import { Form, Link } from "react-router";
import { Badge } from "~/components/ui/badge";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from "~/components/ui/breadcrumb";
import { cn } from "~/lib/utils";
import { metaTitle } from "~/utils";
import type { Route } from "./+types/create-private-git-service";

export function meta() {
  return [
    metaTitle("New Private Git Service")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export default function CreatePrivateGitServicePage({
  params,
  actionData
}: Route.ComponentProps) {
  const [currentStep, setCurrentStep] = React.useState<
    "FORM" | "CREATED" | "DEPLOYED"
  >("FORM");
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
                to={`/project/${params.projectSlug}/${params.envSlug}/create-service`}
                prefetch="intent"
              >
                Create service
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>

          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>Git private</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      {currentStep === "FORM" && (
        <StepServiceForm
          actionData={actionData}
          onSuccess={(slug) => {
            setCurrentStep("CREATED");
            // setServiceSlug(slug);
          }}
        />
      )}
    </>
  );
}

type StepServiceFormProps = {
  onSuccess: (slug: string) => void;
  actionData?: Route.ComponentProps["actionData"];
};

function StepServiceForm({ onSuccess, actionData }: StepServiceFormProps) {
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
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
            <span>private</span>
          </Badge>
        </div>
      </div>
    </Form>
  );
}

export async function clientAction({ request }: Route.ClientActionArgs) {}
