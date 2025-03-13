import { AlertCircle, LoaderIcon } from "lucide-react";
import { Form, redirect, useNavigation } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { Logo } from "~/components/logo";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { SubmitButton } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import { userQueries } from "~/lib/queries";
import { getFormErrorsFromResponseData } from "~/lib/utils";
import { queryClient } from "~/root";
import { metaTitle } from "~/utils";
import whiteLogo from "/logo/Zane-Ops-logo-white-text.svg";
import type { Route } from "./+types/login";

export const meta: Route.MetaFunction = () => [
  metaTitle("Initial Registration")
];

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const userExistQuery = await queryClient.ensureQueryData(
    userQueries.checkUserExistence
  );

  if (userExistQuery.data?.exists) {
    throw redirect("/login");
  }
  return;
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const formData = await request.formData();

  const credentials = {
    username: formData.get("username")!.toString(),
    password: formData.get("password")!.toString()
  };
  const { error: errors, data } = await apiClient.POST(
    "/api/auth/create-initial-user/",
    {
      body: credentials
    }
  );
  if (errors) {
    return {
      errors,
      userData: credentials
    };
  }

  queryClient.removeQueries(userQueries.checkUserExistence);
  queryClient.removeQueries(userQueries.authedUser);

  toast.success("Success", {
    description: data.detail,
    closeButton: true
  });

  throw redirect("/");
}

export default function InitialRegistration({
  actionData
}: Route.ComponentProps) {
  const navigation = useNavigation();

  const isPending =
    navigation.state === "loading" || navigation.state === "submitting";

  const errors = getFormErrorsFromResponseData(actionData?.errors);

  return (
    <>
      <main className="h-[100vh] flex md:flex-row flex-col  justify-center items-center">
        <Logo className="md:hidden" />
        <div className="md:flex hidden flex-col px-20  bg-card md:w-[50%] w-full md:h-screen  h-[50vh]  justify-center ">
          <img
            className="md:w-[180px]  md:fit h-[110px] w-[110px]"
            src={whiteLogo}
            alt="logo"
          />
          <p className="text-white px-5 ">
            your all-in-one platform for deploying your apps with ✨ zen ✨.
          </p>
        </div>

        <Form
          method="POST"
          className="p-7 lg:px-32 md:px-20 md:w-[50%]  flex flex-col w-full"
        >
          <h1 className="md:text-2xl text-3xl md:text-left text-center font-bold my-3">
            Create a user
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
                defaultValue={actionData?.userData?.username}
                type="text"
                aria-describedby="username-error"
                aria-invalid={!!errors.username}
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
                defaultValue={actionData?.userData?.password}
                aria-invalid={!!errors.password}
                aria-describedby="password-error"
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
                  <span>Creating...</span>
                  <LoaderIcon className="animate-spin" size={15} />
                </>
              ) : (
                "Create"
              )}
            </SubmitButton>
          </div>
        </Form>
      </main>
    </>
  );
}
