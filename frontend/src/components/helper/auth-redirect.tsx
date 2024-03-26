import { useNavigate } from "@tanstack/react-router";
import type { ComponentType } from "react";
import { useAuthUser } from "~/components/helper/use-auth-user";
import { Loader } from "~/components/loader";

export function withAuthRedirect(WrappedComponent: ComponentType<any>) {
  return function AuthRedirectWrapper(props: any) {
    const navigate = useNavigate();

    const query = useAuthUser();

    if (query.isLoading) {
      return <Loader />;
    }

    const user = query.data?.data?.user;
    if (!user) {
      navigate({ to: "/login" });
      return null;
    }

    return <WrappedComponent {...props} />;
  };
}
