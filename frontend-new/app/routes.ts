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
    route("create-project", "./routes/projects/create-project.tsx"),
    ...prefix("project", [
      route(":projectSlug", "./routes/projects/project-detail.tsx"),
      route(
        ":projectSlug/create-service",
        "./routes/services/create-service.tsx"
      ),
      route(
        ":projectSlug/create-service/docker",
        "./routes/services/create-docker-service.tsx"
      )
    ])
  ])
] satisfies RouteConfig;
