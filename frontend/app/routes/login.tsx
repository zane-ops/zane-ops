import { AlertCircle, LoaderIcon, MailCheckIcon } from "lucide-react";
import {
  Form,
  href,
  redirect,
  useNavigation,
  useSearchParams
} from "react-router";
import { apiClient } from "~/api/client";
import { ThemedLogo } from "~/components/logo";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel,
  FieldSetPasswordToggleInput
} from "~/components/ui/fieldset";
import { createDevLogger } from "~/lib/logger";
import { userQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  getCsrfTokenHeader,
  getFormErrorsFromResponseData,
  metaTitle
} from "~/lib/utils";
import whiteLogo from "/logo/Zane-Ops-logo-white-text.svg";
import type { Route } from "./+types/login";

export const meta: Route.MetaFunction = () => [metaTitle("Login")];

const logger = createDevLogger(import.meta.url);

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  const [user, userExistQuery] = await Promise.all([
    queryClient.ensureQueryData(userQueries.authedUser),
    queryClient.ensureQueryData(userQueries.checkUserExistence)
  ]);

  if (!userExistQuery.data?.exists) {
    logger.info(`redirect to \`/onboarding\``);
    throw redirect(href("/onboarding"));
  }

  const searchParams = new URL(request.url).searchParams;

  if (user) {
    const redirect_to = searchParams.get("redirect_to");
    let redirectTo = href("/");
    if (redirect_to && URL.canParse(redirect_to, window.location.href)) {
      redirectTo = redirect_to;
    }

    logger.info(`redirect to \`/${redirectTo}\``);
    throw redirect(redirectTo);
  }
  return;
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
  const formData = await request.formData();
  const searchParams = new URL(request.url).searchParams;

  const credentials = {
    username: formData.get("username")?.toString() ?? "",
    password: formData.get("password")?.toString() ?? ""
  };

  const { error: errors, data } = await apiClient.POST("/api/auth/login/", {
    headers: {
      ...(await getCsrfTokenHeader())
    },
    body: credentials
  });
  if (errors) {
    return {
      errors,
      userData: credentials
    };
  }
  if (data?.success) {
    queryClient.removeQueries(userQueries.memberships);
    queryClient.removeQueries(userQueries.authedUser);

    const redirect_to = searchParams.get("redirect_to");

    let redirectTo = href("/");

    if (redirect_to && URL.canParse(redirect_to, window.location.href)) {
      redirectTo = redirect_to;
    }

    throw redirect(redirectTo);
  }
}

export default function LoginPage({ actionData }: Route.ComponentProps) {
  const navigation = useNavigation();
  const isPending =
    navigation.state === "loading" || navigation.state === "submitting";
  const errors = getFormErrorsFromResponseData(actionData?.errors);

  const [searchParams] = useSearchParams();

  const redirectParam = searchParams.get("redirect_to");

  const hasBeenInvited =
    redirectParam &&
    URL.canParse(redirectParam, window.location.href) &&
    redirectParam.startsWith("/invite");

  return (
    <>
      <main className="h-[100vh] flex md:flex-row flex-col  justify-center items-center">
        <ThemedLogo className="md:hidden" />
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
          {hasBeenInvited && (
            <Alert className="p-4" variant="info">
              <MailCheckIcon className="size-4 flex-none" />
              <AlertTitle>Looks like you've been invited!</AlertTitle>
              <AlertDescription>
                Log in to accept the invitation
              </AlertDescription>
            </Alert>
          )}

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

            <FieldSet
              errors={errors.username}
              name="username"
              className="my-2 flex flex-col gap-1"
            >
              <FieldSetLabel>Username</FieldSetLabel>
              <FieldSetInput
                placeholder="ex: JohnDoe"
                defaultValue={actionData?.userData?.username}
              />
            </FieldSet>

            <FieldSet
              name="password"
              errors={errors.password}
              className="flex flex-col gap-1"
            >
              <FieldSetLabel>Password</FieldSetLabel>
              <FieldSetPasswordToggleInput
                defaultValue={actionData?.userData?.password}
              />
            </FieldSet>

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
        </Form>
      </main>
    </>
  );
}
