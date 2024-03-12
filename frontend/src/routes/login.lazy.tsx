import * as Form from "@radix-ui/react-form";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createLazyFileRoute, useNavigate } from "@tanstack/react-router";
import { RequestInput, apiClient } from "~/api/client";
import { Input } from "~/components/ui/input";
import whiteLogo from "/logo/Zane-Ops-logo-white-text.svg";
import logoSymbol from "/logo/ZaneOps-SYMBOL-BLACK.svg";

export const Route = createLazyFileRoute("/login")({
  component: Login
});

function Login() {
  const navigate = useNavigate();

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
        return queryClient.removeQueries({
          queryKey: ["AUTHED_USER"]
        });
      }
      return await navigate({ to: "/" });
    }
  });

  return (
    <>
      <div className="h-[100vh] flex md:flex-row flex-col  justify-center items-center">
        <div className="md:hidden flex justify-center items-center ">
          <img
            className="md:w-[180px]  md:fit h-[110px] w-[110px]"
            src={logoSymbol}
            alt="logo"
          />
        </div>
        <div className="md:flex hidden flex-col px-20 bg-slate-900 md:w-[50%] w-full md:h-screen  h-[50vh]  justify-center ">
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
          className="p-7 md:px-32 md:w-[50%]  flex flex-col w-full"
          action={(formData) =>
            mutate({
              username: formData.get("username")!.toString(),
              password: formData.get("password")!.toString()
            })
          }
        >
          <h1 className="md:text-2xl text-3xl md:text-left text-center font-bold my-3">
            Log in
          </h1>
          <div className="card flex flex-col gap-3">
            <Form.Root>
              {data?.errors && (
                <Form.Message
                  className="text-red-500 text-sm"
                  match={"valueMissing"}
                >
                  {data.errors.root}
                </Form.Message>
              )}

              <Form.Field className="my-5" name="username">
                {!!data?.errors?.username && (
                  <Form.Message
                    className="text-red-500 text-sm"
                    match={"valueMissing"}
                  >
                    {data.errors.username}
                  </Form.Message>
                )}

                <Form.Control asChild>
                  <Input
                    placeholder="username"
                    aria-label="username"
                    name="username"
                    type="text"
                  />
                </Form.Control>
              </Form.Field>

              <Form.Field className="my-5" name="password">
                <Form.Control asChild>
                  <Input
                    aria-label="password"
                    placeholder="password"
                    type="password"
                    name="password"
                  />
                </Form.Control>
                {!!data?.errors?.password && (
                  <Form.Message
                    className="text-red-500 text-sm"
                    match={"valueMissing"}
                  >
                    {data.errors.password}
                  </Form.Message>
                )}
              </Form.Field>

              <Form.Submit asChild>
                <button
                  className="bg-slate-900  w-full p-3 text-white rounded-lg"
                  disabled={isPending}
                >
                  {isPending ? "Submitting..." : "Submit"}
                </button>
              </Form.Submit>
            </Form.Root>
          </div>
        </form>
      </div>
    </>
  );
}

/**
 * 
 * function Error({ errors }) {
  return (
    <div className="text-red-500 text-sm">
      {errors["."] as unknown as string[]}
    </div>
  );
}



  <div>
              <Input
                placeholder="username"
                aria-label="username"
                name="username"
                type="text"
              />
              {!!data?.errors?.username && (
                <p className="text-red-500 text-sm">
                  {data.errors.username as unknown as string[]}
                </p>
              )}
            </div>
            <div>
              <Input
                aria-label="password"
                placeholder="password"
                type="password"
                name="password"
              />
              {!!data?.errors?.password && (
                <p className="text-red-500 text-sm">
                  {data.errors.password as unknown as string[]}
                </p>
              )}
            </div>
            <button
              className="bg-slate-900  w-full p-3 text-white rounded-lg"
              disabled={isPending}
            >
              {isPending ? "Submitting..." : "Submit"}
            </button>

 */
