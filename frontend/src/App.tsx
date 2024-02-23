import "./App.css";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type RequestInput, apiClient, ApiResponse } from "./api/client";
import { deleteCookie, getCookie } from "./utils";

export function App() {
  const query = useQuery({
    queryKey: ["AUTHED_USER"],
    queryFn: ({ signal }) => {
      return apiClient.GET("/api/auth/me/", { signal });
    }
  });
  if (!query.data) {
    return <div>Loading...</div>;
  }

  const authedUser = query.data.data?.user;
  return authedUser ? <AuthedView user={authedUser} /> : <LoginForm />;
}

function AuthedView({ user }: ApiResponse<"get", "/api/auth/me/">) {
  const queryClient = useQueryClient();
  const { data, isPending, mutate } = useMutation({
    mutationFn: async () => {
      // set csrf cookie token
      await apiClient.GET("/api/csrf/");
      const csrfToken = getCookie("csrftoken");
      const { error } = await apiClient.DELETE("/api/auth/logout/", {
        headers: {
          "X-CSRFToken": csrfToken
        }
      });
      if (error) {
        return error;
      }

      queryClient.invalidateQueries({
        queryKey: ["AUTHED_USER"]
      });
      deleteCookie("csrftoken");
    }
  });
  return (
    <dl>
      <h1>
        Welcome, <span style={{ color: "dodgerblue" }}>{user.username}</span>
      </h1>

      <form action={() => mutate()}>
        <button disabled={isPending}>
          {isPending ? "Logging out..." : "Logout"}
        </button>

        {data?.detail && <div style={{ color: "red" }}>{data.detail}</div>}
      </form>
    </dl>
  );
}

function LoginForm() {
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
      action={(formData) =>
        mutate({
          username: formData.get("username")!.toString(),
          password: formData.get("password")!.toString()
        })
      }
    >
      <h1>Login</h1>
      <div className="card">
        {data?.errors && (
          <div style={{ color: "red" }}>
            {data.errors["."] as unknown as string[]}
          </div>
        )}
        <div>
          <label htmlFor="username">username</label>
          <input name="username" type="text" />
          {!!data?.errors?.username && (
            <p style={{ color: "red" }}>
              {data.errors.username as unknown as string[]}
            </p>
          )}
        </div>
        <div>
          <label htmlFor="password">Password</label>
          <input name="password" type="password" />
          {!!data?.errors?.password && (
            <p style={{ color: "red" }}>
              {data.errors.password as unknown as string[]}
            </p>
          )}
        </div>
        <button disabled={isPending}>
          {isPending ? "Submitting..." : "Submit"}
        </button>
      </div>
    </form>
  );
}
