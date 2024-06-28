import * as Form from "@radix-ui/react-form";
import { createFileRoute } from "@tanstack/react-router";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import { useAuthUser } from "~/components/helper/use-auth-user";
import { MetaTitle } from "~/components/meta-title";
import { Button } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import { Textarea } from "~/components/ui/textarea";

export const Route = createFileRoute("/_dashboard/create-project")({
  component: withAuthRedirect(AuthedView)
});

function AuthedView() {
  const query = useAuthUser();
  const user = query.data?.data?.user;

  if (!user) {
    return null;
  }

  return (
    <dl>
      <h1>
        <MetaTitle title="Create Project" />
        <CreateProject />
      </h1>
    </dl>
  );
}

export function CreateProject() {
  return (
    <>
      <Form.Root className="flex h-[60vh] flex-grow justify-center items-center">
        <div className="card flex lg:w-[30%] md:w-[50%] w-full flex-col gap-3">
          <h1 className="text-3xl font-bold">New Project</h1>
          <Form.Field className="my-2 flex flex-col gap-1" name="username">
            <Form.Label>Slug</Form.Label>
            <Form.Control asChild>
              <Input
                className="p-1.5"
                placeholder="Ex: Zaneops"
                name="slug"
                type="text"
              />
            </Form.Control>
          </Form.Field>

          <Form.Field className="my-2 flex flex-col gap-1" name="username">
            <Form.Label>Description</Form.Label>
            <Form.Control asChild>
              <Textarea
                className="placeholder:text-gray-400"
                name="description"
                placeholder="Ex: A self hosted PaaS"
              />
            </Form.Control>
          </Form.Field>

          <Form.Submit asChild>
            <div>
              <Button className="lg:w-fit w-full lg:float-right  p-3 rounded-lg">
                Create a new project
              </Button>
            </div>
          </Form.Submit>
        </div>
      </Form.Root>
    </>
  );
}
