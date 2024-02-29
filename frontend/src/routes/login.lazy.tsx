import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createLazyFileRoute } from "@tanstack/react-router";
import { RequestInput, apiClient } from "~/api/client";
import { Input } from "~/components/ui/input";

export const Route = createLazyFileRoute("/login")({
  component: Login
});

function Login() {
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
        return queryClient.invalidateQueries({
          queryKey: ["AUTHED_USER"]
        });
      }

      throw new Error("Unknow Response from api");
    }
  });

  return (
    <form
      className="p-7"
      action={(formData) =>
        mutate({
          username: formData.get("username")!.toString(),
          password: formData.get("password")!.toString()
        })
      }
    >
      <h1 className="text-3xl font-bold my-3">Login</h1>
      <div className="card">
        {data?.errors && (
          <div style={{ color: "red" }}>
            {data.errors["."] as unknown as string[]}
          </div>
        )}
        <div>
          <label htmlFor="username">username</label>
          <Input name="username" type="text" />
          {!!data?.errors?.username && (
            <p style={{ color: "red" }}>
              {data.errors.username as unknown as string[]}
            </p>
          )}
        </div>
        <div>
          <label htmlFor="password">Password</label>
          <Input type="password" name="password" />
          {!!data?.errors?.password && (
            <p style={{ color: "red" }}>
              {data.errors.password as unknown as string[]}
            </p>
          )}
        </div>
        <button
          className="bg-green-600 p-3 text-white rounded-md my-4"
          disabled={isPending}
        >
          {isPending ? "Submitting..." : "Submit"}
        </button>
      </div>
    </form>
  );
}
