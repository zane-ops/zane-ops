import {
  type RouteConfig,
  index,
  layout,
  prefix,
  route
} from "@react-router/dev/routes";

export default [
  route("login", "./routes/login.tsx"),
  route("logout", "./routes/logout.tsx"),

  route(
    "project/:projectSlug/services/:serviceSlug/deploy-service",
    "./routes/services/deploy-service.tsx"
  ),
  route(
    "project/:projectSlug/services/:serviceSlug/discard-multiple-changes",
    "./routes/services/discard-multiple-changes.tsx"
  ),
  route(
    "project/:projectSlug/services/:serviceSlug/discard-change",
    "./routes/services/discard-service-change.tsx"
  ),
  route(
    "project/:projectSlug/services/:serviceSlug/archive-service",
    "./routes/services/archive-service.tsx"
  ),
  route(
    "project/:projectSlug/services/:serviceSlug/toggle-service-state",
    "./routes/services/toggle-service-state.tsx"
  ),

  layout("./routes/layouts/dashboard-layout.tsx", [
    index("./routes/dashboard.tsx"),
    route("settings", "./routes/user-settings.tsx"),
    route("create-project", "./routes/projects/create-project.tsx"),

    ...prefix("project/:projectSlug", [
      route("", "./routes/layouts/project-layout.tsx", [
        index("./routes/projects/project-service-list.tsx"),
        route("settings", "./routes/projects/project-settings.tsx")
      ]),
      route("create-service", "./routes/services/create-service.tsx"),
      route(
        "create-service/docker",
        "./routes/services/create-docker-service.tsx"
      ),

      ...prefix("services/:serviceSlug", [
        route("", "./routes/layouts/service-layout.tsx", [
          index("./routes/services/services-deployment-list.tsx"),
          route(
            "env-variables",
            "./routes/services/services-env-variables.tsx"
          ),
          route("settings", "./routes/services/settings/services-settings.tsx"),
          route("http-logs", "./routes/services/service-http-logs.tsx"),
          route("metrics", "./routes/services/service-metrics.tsx")
        ]),

        route(
          "deployments/:deploymentHash",
          "./routes/layouts/deployment-layout.tsx",
          [
            index("./routes/deployments/deployment-logs.tsx"),
            route("details", "./routes/deployments/deployment-details.tsx"),
            route("http-logs", "./routes/deployments/deployment-http-logs.tsx"),
            route("metrics", "./routes/deployments/deployment-metrics.tsx"),
            route(
              "redeploy",
              "./routes/deployments/redeploy-old-deployment.tsx"
            ),
            route("cancel", "./routes/deployments/cancel-deployment.tsx")
          ]
        )
      ])
    ])
  ])
] satisfies RouteConfig;
