import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { type RequestInput, apiClient } from "~/api/client";
import { SubmitButton } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import whiteLogo from "/logo/Zane-Ops-logo-white-text.svg";

import { AlertCircle, LoaderIcon } from "lucide-react";
import { useActionState } from "react";
import { Loader } from "~/components/loader";
import { Logo } from "~/components/logo";
import { MetaTitle } from "~/components/meta-title";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { userQueries } from "~/lib/queries";
import { getFormErrorsFromResponseData } from "~/lib/utils";

export const Route = createFileRoute("/login")({
  component: Login
});

function Login() {
  const navigate = useNavigate();
  const redirect_to = Route.useSearch({
    select(s) {
      return (s as { redirect_to?: string }).redirect_to as string;
    }
  });

  const query = useQuery(userQueries.authedUser);
  const user = query.data?.data?.user;

  const queryClient = useQueryClient();
  const { mutateAsync, data } = useMutation({
    mutationFn: async (input: RequestInput<"post", "/api/auth/login/">) => {
      const { error, data } = await apiClient.POST("/api/auth/login/", {
        body: input
      });
      if (error) {
        return error;
      }
      if (data?.success) {
        queryClient.removeQueries(userQueries.authedUser);

        let redirectTo = "/";
        if (redirect_to && URL.canParse(redirect_to, window.location.href)) {
          redirectTo = redirect_to;
        }

        navigate({ to: redirectTo });
        return;
      }
    }
  });

  const [state, formAction, isPending] = useActionState(
    async (prev: any, formData: FormData) => {
      const credentials = {
        username: formData.get("username")!.toString(),
        password: formData.get("password")!.toString()
      };
      const errors = await mutateAsync(credentials);

      if (errors) {
        return credentials;
      }
    },
    null
  );

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

        <form
          action={formAction}
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

            <div className="my-2 flex flex-col gap-1">
              <label htmlFor="username" className="">
                Username
              </label>
              <Input
                id="username"
                name="username"
                placeholder="ex: JohnDoe"
                defaultValue={state?.username}
                type="text"
                aria-describedby="username-error"
              />
              {errors.username && (
                <span id="username-error" className="text-red-500 text-sm">
                  {errors.username}
                </span>
              )}
            </div>

            <div className="flex flex-col gap-1">
              <label htmlFor="password">Password</label>
              <Input
                type="password"
                name="password"
                id="password"
                defaultValue={state?.password}
              />
              {errors.password && (
                <span id="password-error" className="text-red-500 text-sm">
                  {errors.password}
                </span>
              )}
            </div>

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
          </div>
        </form>
      </div>
    </>
  );
}
