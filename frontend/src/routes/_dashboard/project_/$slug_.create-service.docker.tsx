import * as Form from "@radix-ui/react-form";
import { Link, createFileRoute } from "@tanstack/react-router";
import { ArrowRight, Check } from "lucide-react";
import * as React from "react";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from "~/components/ui/breadcrumb";
import { Button } from "~/components/ui/button";
import {
  Command,
  CommandInput,
  CommandItem,
  CommandList
} from "~/components/ui/command";
import { Input } from "~/components/ui/input";

export const Route = createFileRoute(
  "/_dashboard/project/$slug/create-service/docker"
)({
  component: withAuthRedirect(Docker)
});

function Docker() {
  const { slug } = Route.useParams();
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
            <BreadcrumbLink asChild>
              <Link to={`/project/${slug}`} className="capitalize">
                {slug}
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>

          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to={`/project/${slug}/create-service`}>Create service</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>

          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>Docker</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <StepServiceForm />
    </main>
  );
}

function StepServiceForm() {
  const [isComboxOpen, setComboxOpen] = React.useState(false);

  return (
    <Form.Root className="flex mt-10 flex-grow justify-center items-center">
      <div className="card flex lg:w-[30%] md:w-[50%] w-full flex-col gap-3">
        <h1 className="text-3xl font-bold">New Service</h1>

        <Form.Field className="my-2 flex flex-col gap-1" name="username">
          <Form.Label>Slug</Form.Label>
          <Form.Control asChild>
            <Input
              className="p-3"
              placeholder="ex: db"
              name="slug"
              type="text"
            />
          </Form.Control>
        </Form.Field>

        <Form.Field className="my-2 flex flex-col gap-1" name="username">
          <Form.Label>Image</Form.Label>
          <Form.Control asChild>
            <Command>
              <CommandInput
                onFocus={() => setComboxOpen(true)}
                onBlur={() => setComboxOpen(false)}
                className="p-3"
                placeholder="ex: bitnami/redis"
                name="image"
              />
              {isComboxOpen && (
                <CommandList>
                  <CommandItem>valkey/valkey</CommandItem>
                  <CommandItem>postgres:alpine</CommandItem>
                  <CommandItem>example/example</CommandItem>
                  <CommandItem>caddy:caddy</CommandItem>
                </CommandList>
              )}
            </Command>
          </Form.Control>
        </Form.Field>

        <div className="flex flex-col gap-3">
          <h1 className="text-lg">
            Credentials <span className="text-gray-400">(optional)</span>
          </h1>
          <p className="text-gray-400">
            If your image is on a private registry, please provide these
            information below.
          </p>
        </div>

        <Form.Field className="my-2 flex flex-col gap-1" name="username">
          <Form.Label>Username for registry</Form.Label>
          <Form.Control asChild>
            <Input
              className="p-3"
              placeholder="ex: mocherif"
              name="slug"
              type="text"
            />
          </Form.Control>
        </Form.Field>

        <Form.Field className="my-2 flex flex-col gap-1" name="username">
          <Form.Label>Password for registry</Form.Label>
          <Form.Control asChild>
            <Input
              className="p-3"
              placeholder="************"
              name="slug"
              type="text"
            />
          </Form.Control>
        </Form.Field>

        <Form.Submit asChild>
          <Button className="p-3 rounded-lg">Create New Service</Button>
        </Form.Submit>
      </div>
    </Form.Root>
  );
}

function StepServiceCreated({
  slug,
  serviceSlug
}: { slug: string; serviceSlug: string }) {
  return (
    <div className="flex  flex-col h-[70vh] justify-center items-center">
      <div className="flex flex-col gap-4 lg:w-1/3 md:w-1/2 w-full">
        <Alert variant="success">
          <Check className="h-5 w-5 text-green-400" />
          <AlertTitle className="text-lg">Success</AlertTitle>

          <AlertDescription>
            Service <span className="capitalize">`{serviceSlug}`</span> Created
            Successfuly
          </AlertDescription>
        </Alert>

        <div className="flex gap-3 md:flex-row flex-col items-stretch">
          <Button asChild className="flex-1">
            <Link className="flex gap-2 items-center" to="">
              Deploy Now
            </Link>
          </Button>

          <Button asChild className="flex-1" variant="outline">
            <Link
              to={`/project/${slug}/services/docker/${serviceSlug}`}
              className="flex gap-2  items-center"
            >
              Go to service details <ArrowRight size={20} />
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}

function StepServiceDeployed({
  slug,
  serviceSlug
}: { slug: string; serviceSlug: string }) {
  return (
    <div className="flex  flex-col h-[70vh] justify-center items-center">
      <div className="flex flex-col gap-4 lg:w-1/3 md:w-1/2 w-full">
        <Alert variant="success">
          <Check className="h-5 w-5 text-green-400" />
          <AlertTitle className="text-lg">Success</AlertTitle>

          <AlertDescription>
            Service <span className="capitalize">`{serviceSlug}`</span> Deployed
            Successfuly
          </AlertDescription>
        </Alert>

        <div className="flex gap-3 md:flex-row flex-col items-stretch">
          <Button asChild className="flex-1">
            <Link
              to={`/project/${slug}/services/docker/${serviceSlug}`}
              className="flex gap-2  items-center"
            >
              Go to service details <ArrowRight size={20} />
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
