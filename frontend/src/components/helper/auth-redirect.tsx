import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { ComponentType, ReactElement, useEffect } from "react";
import { apiClient } from "../../api/client";

export function withAuthRedirect(WrappedComponent: ComponentType<any>) {
  return function AuthRedirectWrapper(props: ReactElement) {
    const navigate = useNavigate();

    const query = useQuery({
      queryKey: ["AUTHED_USER"],
      queryFn: ({ signal }) => {
        return apiClient.GET("/api/auth/me/", { signal });
      }
    });

    useEffect(() => {
      if (query.data?.data?.user) {
        return;
      }
      navigate({ to: "/login" });
    }, [query.data, navigate]);

    if (query.isLoading) {
      return <div className="text-3xl font-bold">Loading... with tailwind</div>;
    }

    return <WrappedComponent {...props} />;
  };
}
