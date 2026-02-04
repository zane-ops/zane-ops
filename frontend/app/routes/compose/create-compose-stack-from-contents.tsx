import { LoaderIcon } from "lucide-react";
import * as React from "react";
import { Form, Link, href, useNavigation } from "react-router";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from "~/components/ui/breadcrumb";
import { SubmitButton } from "~/components/ui/button";
import { CodeEditor } from "~/components/ui/code-editor";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel,
  FieldSetTextarea
} from "~/components/ui/fieldset";
import { useLocalStorage } from "~/lib/use-local-storage";
import { cn } from "~/lib/utils";
import { metaTitle } from "~/utils";
import type { Route } from "./+types/create-compose-stack-from-contents";

export function meta() {
  return [
    metaTitle("New Compose Stack")
  ] satisfies ReturnType<Route.MetaFunction>;
}

const SAVED_COMPOSE_CONTENTS_KEY = "compose:last-user-contents";

export default function CreateComposeStackFromContentsPage({
  params,
  actionData
}: Route.ComponentProps) {
  const [currentStep, setCurrentStep] = React.useState<
    "FORM" | "CREATED" | "DEPLOYED"
  >("FORM");

  const [composeStackSlug, setComposeStackSlug] = React.useState("");
  const [deploymentHash, setDeploymentHash] = React.useState("");
  const [, setUserContents] = useLocalStorage(SAVED_COMPOSE_CONTENTS_KEY, "");

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
                to={href("/project/:projectSlug/:envSlug", {
                  ...params,
                  envSlug: "production"
                })}
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
                to={href("/project/:projectSlug/:envSlug", params)}
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
            <BreadcrumbPage>From compose contents</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      {currentStep === "FORM" && (
        <FormStep
          actionData={actionData}
          onSuccess={(slug) => {
            setCurrentStep("CREATED");
            setComposeStackSlug(slug);
          }}
        />
      )}
    </>
  );
}

type FormStepProps = {
  onSuccess: (slug: string) => void;
  actionData?: Route.ComponentProps["actionData"];
};

function FormStep({ actionData, onSuccess }: FormStepProps) {
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const navigation = useNavigation();
  const isPending = navigation.state === "submitting";

  const [userContents, setUserContents] = useLocalStorage(
    SAVED_COMPOSE_CONTENTS_KEY,
    ""
  );

  return (
    <Form
      ref={formRef}
      method="post"
      className="flex my-10 grow justify-center items-center"
    >
      <div className="card flex  md:w-[50%] w-full flex-col gap-5 items-stretch">
        <h1 className="text-3xl font-bold">New Compose stack</h1>

        <FieldSet
          name="slug"
          className="my-2 flex flex-col gap-1"
          // errors={errors.slug}
          required
        >
          <FieldSetLabel className="dark:text-card-foreground">
            Slug
          </FieldSetLabel>

          <FieldSetInput
            className="p-3"
            placeholder="ex: immich"
            type="text"
            // defaultValue={actionData?.userData?.slug}
          />
        </FieldSet>

        <FieldSet
          name="user_contents"
          required
          // errors={errors.new_value?.contents}
          className="flex flex-col gap-1.5 flex-1"
        >
          <FieldSetLabel className="dark:text-card-foreground">
            Contents
          </FieldSetLabel>
          <FieldSetTextarea className="sr-only" value={userContents} readOnly />

          <CodeEditor
            containerClassName="w-full h-100"
            language="yaml"
            value={userContents}
            onChange={(value) => setUserContents(value ?? "")}
          />
        </FieldSet>

        <SubmitButton
          className="p-3 rounded-lg gap-2 self-end"
          isPending={isPending}
          name="step"
          value="create-stack"
        >
          {isPending ? (
            <>
              <span>Creating stack...</span>
              <LoaderIcon className="animate-spin" size={15} />
            </>
          ) : (
            "Create New Stack"
          )}
        </SubmitButton>
      </div>
    </Form>
  );
}
