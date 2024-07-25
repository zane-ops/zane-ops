import * as Form from "@radix-ui/react-form";
import { createFileRoute } from "@tanstack/react-router";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import { Button } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import { Textarea } from "~/components/ui/textarea";

export const Route = createFileRoute("/_dashboard/project/docker")({
  component: withAuthRedirect(Docker)
});

function Docker() {
  return (
    <main>
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
              <Input
                className="p-3"
                placeholder="ex: postgres/postgres:12-alpine"
                name="slug"
                type="text"
              />
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
                placeholder="ex: fredhelkissie"
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
    </main>
  );
}
