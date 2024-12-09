import {
  type RouteConfig,
  index,
  layout,
  route
} from "@react-router/dev/routes";

export default [
  route("login", "./routes/login.tsx"),
  layout("./routes/layouts/dashboard.tsx", [index("routes/home.tsx")])
] satisfies RouteConfig;
