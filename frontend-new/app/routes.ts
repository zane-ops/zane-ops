import {
  type RouteConfig,
  index,
  layout,
  prefix,
  route
} from "@react-router/dev/routes";

export default [
  route("login", "./routes/login.tsx"),
  layout("./routes/layouts/dashboard.tsx", [
    index("./routes/home.tsx"),
    ...prefix("project", [
      route(":projectSlug", "./routes/projects/project-detail.tsx")
    ])
  ])
] satisfies RouteConfig;
