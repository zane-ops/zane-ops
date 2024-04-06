import * as Form from "@radix-ui/react-form";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createLazyFileRoute, useNavigate } from "@tanstack/react-router";
import { type RequestInput, apiClient } from "~/api/client";
import { Button } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import whiteLogo from "/logo/Zane-Ops-logo-white-text.svg";

import { AlertCircle } from "lucide-react";
import { useAuthUser } from "~/components/helper/use-auth-user";
import { Loader } from "~/components/loader";
import { Logo } from "~/components/logo";
import { MetaTitle } from "~/components/meta-title";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { userKeys } from "~/key-factories";

export const Route = createLazyFileRoute("/login")({
  component: Login
});

function Login() {
  const navigate = useNavigate();
  const query = useAuthUser();
  const user = query.data?.data?.user;

  const queryClient = useQueryClient();
  const { isPending, mutate, data } = useMutation({
    mutationFn: async (input: RequestInput<"post", "/api/auth/login/">) => {
      const { error, data } = await apiClient.POST("/api/auth/login/", {
        body: input
      });
      if (error) {
        return error;
      }
      if (data?.success) {
        queryClient.removeQueries({
          queryKey: userKeys.authedUser
        });
        navigate({ to: "/" });
        return;
      }
    }
  });

  if (query.isLoading) {
    return <Loader />;
  }

  if (user) {
    navigate({ to: "/" });
    return null;
  }

  return (
    <>
      <MetaTitle title="Login" />
      <div className="h-[100vh] flex md:flex-row flex-col  justify-center items-center">
        <Logo className="md:hidden" />
        <div className="md:flex hidden flex-col px-20  bg-card md:w-[50%] w-full md:h-screen  h-[50vh]  justify-center ">
          <img
            className="md:w-[180px]  md:fit h-[110px] w-[110px]"
            src={whiteLogo}
            alt="logo"
          />
          <p className="text-white px-5 ">
            Embrace ZaneOps, Your Self-Hosted PaaS Solution for Seamless Web
            Service Management.
          </p>
        </div>

        <Form.Root
          autoComplete="off"
          action={(formData) =>
            mutate({
              username: formData.get("username")!.toString(),
              password: formData.get("password")!.toString()
            })
          }
          className="p-7 lg:px-32 md:px-20 md:w-[50%]  flex flex-col w-full"
        >
          <h1 className="md:text-2xl text-3xl md:text-left text-center font-bold my-3">
            Log in
          </h1>
          <div className="card flex flex-col gap-3">
            {data?.errors?.root && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Error</AlertTitle>
                <AlertDescription>{data.errors.root}</AlertDescription>
              </Alert>
            )}

            <Form.Field className="my-2 flex flex-col gap-1" name="username">
              <Form.Label className="">Username</Form.Label>
              <Form.Control asChild>
                <Input placeholder="ex: JohnDoe" name="username" type="text" />
              </Form.Control>
              {data?.errors?.username && (
                <Form.Message className="text-red-500 text-sm">
                  {data.errors.username}
                </Form.Message>
              )}
            </Form.Field>

            <Form.Field className="flex flex-col gap-1" name="password">
              <Form.Label>Password</Form.Label>
              <Form.Control asChild>
                <Input type="password" name="password" />
              </Form.Control>
              {data?.errors?.password && (
                <Form.Message className="text-red-500 text-sm">
                  {data.errors.password}
                </Form.Message>
              )}
            </Form.Field>

            <Form.Submit asChild>
              <Button className="w-full p-3 rounded-lg" disabled={isPending}>
                {isPending ? "Submitting..." : "Submit"}
              </Button>
            </Form.Submit>
          </div>
        </Form.Root>
      </div>
    </>
  );
}
