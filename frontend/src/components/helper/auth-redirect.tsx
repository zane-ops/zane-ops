import { useNavigate } from "@tanstack/react-router";
import { ComponentType, ReactElement } from "react";
import { useAuthUser } from "~/components/helper/use-auth-user";

export function withAuthRedirect(WrappedComponent: ComponentType<any>) {
  return function AuthRedirectWrapper(props: ReactElement) {
    const navigate = useNavigate();

    const query = useAuthUser();

    if (query.isLoading) {
      return <div className="text-3xl font-bold">Loading... with tailwind</div>;
    }

    const user = query.data?.data?.user;
    if (!user) {
      navigate({ to: "/login" });
      return null;
    }
    return <WrappedComponent {...props} />;
  };
}
