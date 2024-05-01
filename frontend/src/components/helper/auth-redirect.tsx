import { useNavigate } from "@tanstack/react-router";
import { useAuthUser } from "~/components/helper/use-auth-user";
import { Loader } from "~/components/loader";

import type { ComponentType } from "react";

export function withAuthRedirect(WrappedComponent: ComponentType) {
  return function AuthRedirectWrapper(props: any) {
    const navigate = useNavigate();

    const query = useAuthUser();

    if (query.isLoading) return <Loader />;

    const user = query.data?.data?.user;

    if (!user) {
      navigate({ to: "/login" });
      return null;
    }

    return <WrappedComponent {...props} />;
  };
}
