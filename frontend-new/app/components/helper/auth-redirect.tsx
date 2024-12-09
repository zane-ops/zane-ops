import { useQuery } from "@tanstack/react-query";
import type { ComponentType } from "react";
import { useNavigate } from "react-router";
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

      const sp = new URLSearchParams();
      if (currentPath !== "/login") {
        sp.append("redirect_to", currentPath);
      }
      navigate(`/login?${sp.toString()}`);
      return null;
    }

    return <WrappedComponent {...props} />;
  };
}
