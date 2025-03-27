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
  route("onboarding", "./routes/onboarding.tsx"),
  route("trigger-update", "./routes/trigger-update.tsx"),

  route(
    "project/:projectSlug/:envSlug/services/:serviceSlug/deploy-docker-service",
    "./routes/services/deploy-docker-service.tsx"
  ),
  route(
    "project/:projectSlug/:envSlug/services/:serviceSlug/deploy-git-service",
    "./routes/services/deploy-git-service.tsx"
  ),
  route(
    "project/:projectSlug/:envSlug/services/:serviceSlug/discard-multiple-changes",
    "./routes/services/discard-multiple-changes.tsx"
  ),
  route(
    "project/:projectSlug/:envSlug/services/:serviceSlug/discard-change",
    "./routes/services/discard-service-change.tsx"
  ),
  route(
    "project/:projectSlug/:envSlug/services/:serviceSlug/archive-docker-service",
    "./routes/services/archive-docker-service.tsx"
  ),
  route(
    "project/:projectSlug/:envSlug/services/:serviceSlug/archive-git-service",
    "./routes/services/archive-git-service.tsx"
  ),
  route(
    "project/:projectSlug/:envSlug/services/:serviceSlug/toggle-service-state",
    "./routes/services/toggle-service-state.tsx"
  ),
  route(
    "project/:projectSlug/:envSlug/bulk-toggle-service-state",
    "./routes/projects/bulk-toggle-service-state.tsx"
  ),

  layout("./routes/layouts/dashboard-layout.tsx", [
    index("./routes/dashboard.tsx"),
    route("create-project", "./routes/projects/create-project.tsx"),

    ...prefix("project/:projectSlug/:envSlug", [
      route("", "./routes/layouts/project-layout.tsx", [
        index("./routes/projects/project-service-list.tsx"),
        route("settings", "./routes/projects/project-settings.tsx"),
        route("environments", "./routes/projects/project-environments.tsx"),
        route("variables", "./routes/projects/project-env-variables.tsx")
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
            route(
              "build-logs",
              "./routes/deployments/deployment-build-logs.tsx"
            ),
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
