import { createRootRoute, Link, Outlet } from "@tanstack/react-router";

export const Route = createRootRoute({
  component: () => (
    <>
      <div className="p-2 flex gap-2">
        <Link to="/" className="[&.active]:font-bold">
          Home
        </Link>{" "}
        <Link to="/login" className="[&.active]:font-bold">
          Login
        </Link>
      </div>
      <hr />
      <Outlet />
    </>
  ),
});
