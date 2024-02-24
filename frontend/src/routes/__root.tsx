import { createRootRoute, Link, Outlet } from "@tanstack/react-router";
import { TanStackRouterDevtools } from "@tanstack/router-devtools";

export const Route = createRootRoute({
  component: () => (
    <>
      <div className="p-2 flex gap-2">
        <NavLink href="/" name="Home" />
        <NavLink href="/login" name="Login" />
      </div>
      <hr />
      <Outlet />
      <TanStackRouterDevtools />
    </>
  )
});

function NavLink({ href, name }: { href: string; name: string }) {
  return (
    <>
      <Link
        activeProps={{
          style: {
            fontWeight: "bold"
          }
        }}
        to={href}
      >
        {name}
      </Link>
    </>
  );
}
