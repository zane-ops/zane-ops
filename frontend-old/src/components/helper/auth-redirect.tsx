import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import type { ComponentType } from "react";
import { Loader } from "~/components/loader";
import { userQueries } from "~/lib/queries";

export function withAuthRedirect(WrappedComponent: ComponentType<any>) {
  return function AuthRedirectWrapper(props: any) {
    const navigate = useNavigate();

    const query = useQuery(userQueries.authedUser);

    if (query.isLoading) {
      return <Loader />;
    }

    const user = query.data?.data?.user;
    if (!user) {
      const currentPath = window.location.pathname;

      navigate({
        to: "/login",
        search:
          currentPath !== "/login"
            ? {
                redirect_to: currentPath
              }
            : undefined
      });
      return null;
    }

    return <WrappedComponent {...props} />;
  };
}
