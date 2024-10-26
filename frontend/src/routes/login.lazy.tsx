import * as Form from "@radix-ui/react-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createLazyFileRoute, useNavigate } from "@tanstack/react-router";
import { type RequestInput, apiClient } from "~/api/client";
import { SubmitButton } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import whiteLogo from "/logo/Zane-Ops-logo-white-text.svg";

import { AlertCircle, LoaderIcon } from "lucide-react";
import { Loader } from "~/components/loader";
import { Logo } from "~/components/logo";
import { MetaTitle } from "~/components/meta-title";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { userQueries } from "~/lib/queries";
import { getFormErrorsFromResponseData } from "~/lib/utils";

export const Route = createLazyFileRoute("/login")({
  component: Login
});

function Login() {
  const navigate = useNavigate();
  const query = useQuery(userQueries.authedUser);
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
          queryKey: userQueries.authedUser.queryKey
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

  const errors = getFormErrorsFromResponseData(data);

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
            {errors.non_field_errors && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Error</AlertTitle>
                <AlertDescription>{errors.non_field_errors}</AlertDescription>
              </Alert>
            )}

            <Form.Field className="my-2 flex flex-col gap-1" name="username">
              <Form.Label className="">Username</Form.Label>
              <Form.Control asChild>
                <Input placeholder="ex: JohnDoe" name="username" type="text" />
              </Form.Control>
              {errors.username && (
                <Form.Message className="text-red-500 text-sm">
                  {errors.username}
                </Form.Message>
              )}
            </Form.Field>

            <Form.Field className="flex flex-col gap-1" name="password">
              <Form.Label>Password</Form.Label>
              <Form.Control asChild>
                <Input type="password" name="password" />
              </Form.Control>
              {errors.password && (
                <Form.Message className="text-red-500 text-sm">
                  {errors.password}
                </Form.Message>
              )}
            </Form.Field>

            <Form.Submit asChild>
              <SubmitButton
                className="lg:w-fit w-full lg:ml-auto p-3 rounded-lg gap-2"
                isPending={isPending}
              >
                {isPending ? (
                  <>
                    <span>Submitting...</span>
                    <LoaderIcon className="animate-spin" size={15} />
                  </>
                ) : (
                  "Submit"
                )}
              </SubmitButton>
            </Form.Submit>
          </div>
        </Form.Root>
      </div>
    </>
  );
}
