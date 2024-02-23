import "./App.css";
import { useMutation } from "@tanstack/react-query";
import { apiClient } from "./api/client";
import type { paths } from "./api/v1";

function App() {
  const { data, isPending, mutate } = useMutation({
    mutationFn: async (
      data: paths["/api/auth/login/"]["post"]["requestBody"]["content"]["application/json"]
    ) => {
      return apiClient.POST("/api/auth/login/", {
        body: data
      });
    }
  });

  console.log({
    data
  });
  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        const fd = new FormData(e.currentTarget);
        mutate({
          username: fd.get("username")!.toString(),
          password: fd.get("password")!.toString()
        });
      }}
    >
      <h1>Login</h1>
      <div className="card">
        {data?.error && (
          <div style={{ color: "red" }}>
            {data.error.errors["."] as unknown as string[]}
          </div>
        )}
        <div>
          <label htmlFor="username">username</label>
          <input name="username" type="text" />
        </div>
        <div>
          <label htmlFor="password">Password</label>
          <input name="password" type="password" />
        </div>
        <button disabled={isPending}>
          {isPending ? "Submitting..." : "Submit"}
        </button>
      </div>
    </form>
  );
}

export default App;
