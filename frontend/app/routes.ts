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
    "project/:projectSlug/:envSlug/services/:serviceSlug/cleanup-deploy-queue",
    "./routes/services/cleanup-deploy-queue.tsx"
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
    "./routes/environments/bulk-toggle-service-state.tsx"
  ),
  route(
    "project/:projectSlug/:envSlug/bulk-deploy-services",
    "./routes/environments/bulk-deploy-services.tsx"
  ),

  layout("./routes/layouts/dashboard-layout.tsx", [
    index("./routes/dashboard.tsx"),

    route(
      "/project/:projectSlug/:envSlug/review-deployment",
      "./routes/environments/review-deployment.tsx"
    ),

    route("settings", "./routes/layouts/settings-layout.tsx", [
      index("./routes/settings/settings-index.tsx"),
      route("account", "./routes/settings/account-settings.tsx"),
      route("account/change-password", "./routes/settings/change-password.tsx"),
      route("ssh-keys", "./routes/settings/ssh-keys-list.tsx"),
      route("ssh-keys/new", "./routes/settings/create-ssh-key.tsx"),
      route("server-console", "./routes/settings/server-terminal.tsx"),
      route("git-apps", "./routes/settings/git-apps-list.tsx"),
      route(
        "git-apps/create-github-app",
        "./routes/settings/create-github-app.tsx"
      ),
      route(
        "git-apps/create-gitlab-app",
        "./routes/settings/create-gitlab-app.tsx"
      ),
      route("git-apps/github/:id", "./routes/settings/github-app-details.tsx"),
      route("git-apps/gitlab/:id", "./routes/settings/gitlab-app-details.tsx"),
      route(
        "shared-credentials",
        "./routes/settings/registry-credentials-list.tsx"
      ),
      route(
        "shared-credentials/new",
        "./routes/settings/create-registry-credentials.tsx"
      ),
      route(
        "shared-credentials/:id",
        "./routes/settings/registry-credentials-details.tsx"
      ),
      route("build-registries", "./routes/settings/build-registry-list.tsx")
      // route(
      //   "shared-credentials/new",
      //   "./routes/settings/create-registry-credentials.tsx"
      // ),
      // route(
      //   "shared-credentials/:id",
      //   "./routes/settings/registry-credentials-details.tsx"
      // ),
    ]),
    route("create-project", "./routes/projects/create-project.tsx"),

    ...prefix("project/:projectSlug/settings", [
      route("", "./routes/layouts/project-layout.tsx", [
        index("./routes/projects/project-settings.tsx"),
        route("environments", "./routes/projects/project-environments.tsx"),
        route("preview-templates", "./routes/projects/preview-templates.tsx"),
        route(
          "preview-templates/new",
          "./routes/projects/create-preview-template.tsx"
        ),
        route(
          "preview-templates/:templateSlug",
          "./routes/projects/preview-template-details.tsx"
        ),
        route(
          "preview-templates/:templateSlug/delete",
          "./routes/projects/delete-preview-template.tsx"
        )
      ])
    ]),

    ...prefix("project/:projectSlug/:envSlug", [
      route("", "./routes/layouts/environment-layout.tsx", [
        index("./routes/environments/environment-service-list.tsx"),
        route("variables", "./routes/environments/environment-variables.tsx"),
        route("settings", "./routes/environments/environments-settings.tsx")
      ]),
      route("create-service", "./routes/services/create-service.tsx"),
      route(
        "create-service/docker",
        "./routes/services/create-docker-service.tsx"
      ),
      route(
        "create-service/git-public",
        "./routes/services/create-public-git-service.tsx"
      ),
      route(
        "create-service/git-private",
        "./routes/services/create-private-git-service.tsx"
      ),
      route(
        "create-service/git-private/:gitAppId",
        "./routes/services/create-git-service-from-gitapp.tsx"
      ),

      ...prefix("services/:serviceSlug", [
        route("", "./routes/layouts/service-layout.tsx", [
          index("./routes/services/services-deployment-list.tsx"),
          route(
            "env-variables",
            "./routes/services/services-env-variables.tsx"
          ),
          route("settings", "./routes/services/settings/service-settings.tsx"),
          route("http-logs", "./routes/services/service-http-logs.tsx"),
          route("metrics", "./routes/services/service-metrics.tsx")
        ]),

        route(
          "deployments/:deploymentHash",
          "./routes/layouts/deployment-layout.tsx",
          [
            index("./routes/deployments/deployment-logs.tsx"),
            route("details", "./routes/deployments/deployment-details.tsx"),
            route("terminal", "./routes/deployments/deployment-terminal.tsx"),
            route("http-logs", "./routes/deployments/deployment-http-logs.tsx"),
            route(
              "build-logs",
              "./routes/deployments/deployment-build-logs.tsx"
            ),
            route("metrics", "./routes/deployments/deployment-metrics.tsx"),
            route(
              "redeploy-docker",
              "./routes/deployments/redeploy-docker-deployment.tsx"
            ),
            route(
              "redeploy-git",
              "./routes/deployments/redeploy-git-deployment.tsx"
            ),
            route("cancel", "./routes/deployments/cancel-deployment.tsx")
          ]
        )
      ])
    ])
  ])
] satisfies RouteConfig;
