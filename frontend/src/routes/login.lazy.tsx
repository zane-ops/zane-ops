import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createLazyFileRoute, useNavigate } from "@tanstack/react-router";
import { RequestInput, apiClient } from "~/api/client";
import { Input } from "~/components/ui/input";
import logo from "/logo/Zane Ops logo black.svg";

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
      <div className="h-[100vh]  flex md:flex-row flex-col  justify-center items-center">
        <div className="flex w-[50%] md:h-screen  justify-center items-center">
          <img
            className="md:w-[160px] md:h-[160px] h-[110px] w-[110px]"
            src={logo}
            alt="logo"
          />
        </div>

        <form
          className="p-7 md:w-[50%] w-full"
          action={(formData) =>
            mutate({
              username: formData.get("username")!.toString(),
              password: formData.get("password")!.toString()
            })
          }
        >
          <h1 className="text-2xl font-bold my-3 md:text-left text-center">
            Log in to ZaneOps
          </h1>
          <div className="card flex flex-col gap-3">
            {data?.errors && (
              <div style={{ color: "red" }}>
                {data.errors["."] as unknown as string[]}
              </div>
            )}
            <div>
              <Input
                placeholder="username"
                aria-label="username"
                name="username"
                type="text"
              />
              {!!data?.errors?.username && (
                <p style={{ color: "red" }}>
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
                <p style={{ color: "red" }}>
                  {data.errors.password as unknown as string[]}
                </p>
              )}
            </div>
            <button
              className="bg-black md:w-[60%] w-full p-3 text-white rounded-lg "
              disabled={isPending}
            >
              {isPending ? "Submitting..." : "Submit"}
            </button>
          </div>
        </form>
      </div>
    </>
  );
}
