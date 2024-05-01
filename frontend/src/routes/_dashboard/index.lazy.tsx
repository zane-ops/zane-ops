import { createLazyFileRoute } from "@tanstack/react-router";
import { withAuthRedirect } from "~/components/helper/auth-redirect";
import { useAuthUser } from "~/components/helper/use-auth-user";
import { MetaTitle } from "~/components/meta-title";

import type { FC } from "react";

const AuthedView: FC = () => {
  const query = useAuthUser();
  const user = query.data?.data?.user;

  if (!user) return null;

  return (
    <dl>
      <h1>
        <MetaTitle title="Dashboard" />
        Welcome, <span style={{ color: "dodgerblue" }}>{user.username}</span>
      </h1>
    </dl>
  );
};

export const Route = createLazyFileRoute("/_dashboard/")({
  component: withAuthRedirect(AuthedView)
});
