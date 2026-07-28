import {
  type RouteConfig,
  index,
  layout,
  prefix,
  route
} from "@react-router/dev/routes";

export default [
  route("login", "./routes/login.tsx"),
  route("invite/:token", "./routes/workspace-invitation.tsx"),
  route("logout", "./routes/logout.tsx"),
  route("onboarding", "./routes/onboarding.tsx"),
  route("trigger-update", "./routes/trigger-update.tsx"),
  route("switch-workspace", "./routes/switch-workspace.tsx"),

  layout("./routes/layouts/main-layout.tsx", [
    layout("./routes/layouts/home-layout.tsx", [
      index("./routes/home.tsx"),
      ...prefix("account", [
        index("./routes/settings/account-settings.tsx"),
        route("change-password", "./routes/settings/change-password.tsx")
      ])
    ]),

    ...prefix("workspace", [
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
      )
    ]),

    layout("./routes/layouts/server-admin-layout.tsx", [
      ...prefix("admin", [
        route("ssh-keys", "./routes/server-admin/ssh-keys-list.tsx"),
        route("ssh-keys/new", "./routes/server-admin/create-ssh-key.tsx"),
        route("server-console", "./routes/server-admin/server-terminal.tsx"),
        route(
          "build-registries",
          "./routes/server-admin/build-registry-list.tsx"
        ),
        route(
          "build-registries/new",
          "./routes/server-admin/create-build-registry.tsx"
        ),
        route(
          "build-registries/:id/list-images",
          "./routes/server-admin/build-registry-image-list.tsx"
        ),
        route(
          "build-registries/:id",
          "./routes/server-admin/build-registry-details.tsx"
        )
      ])
    ]),

    ...prefix("workspace", [
      layout("./routes/layouts/workspace-layout.tsx", [
        index("./routes/project-list.tsx"),

        route(
          "project/:projectSlug/:envSlug/review-deployment",
          "./routes/environments/review-deployment.tsx"
        ),

        route("settings", "./routes/layouts/workspace-settings-layout.tsx", [
          index("./routes/settings/workspace-settings.tsx"),

          ...prefix("team", [
            index("./routes/settings/workspace-team-settings.tsx"),
            route("invite", "./routes/settings/invite-user-into-workspace.tsx"),
            route(
              ":id/permissions",
              "./routes/settings/workspace-edit-member-permissions.tsx"
            ),
            route(":id/remove", "./routes/settings/workspace-remove-member.tsx")
          ]),

          route(
            "invitations",
            "./routes/settings/workspace-invitation-list.tsx"
          ),
          route(
            "invitations/:id",
            "./routes/settings/workspace-invitation-details.tsx"
          ),
          route("git-apps", "./routes/settings/git-apps-list.tsx"),
          route(
            "git-apps/create-github-app",
            "./routes/settings/create-github-app.tsx"
          ),
          route(
            "git-apps/create-gitlab-app",
            "./routes/settings/create-gitlab-app.tsx"
          ),
          route(
            "git-apps/github/:id",
            "./routes/settings/github-app-details.tsx"
          ),
          route(
            "git-apps/gitlab/:id",
            "./routes/settings/gitlab-app-details.tsx"
          ),
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
          )
        ]),
        route("create-project", "./routes/projects/create-project.tsx"),

        ...prefix("project/:projectSlug/settings", [
          route("", "./routes/layouts/project-settings-layout.tsx", [
            index("./routes/projects/project-settings.tsx"),
            route(
              "environments",
              "./routes/projects/project-environment-list.tsx"
            ),
            route(
              "preview-templates",
              "./routes/projects/preview-templates.tsx"
            ),
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
            route(
              "variables",
              "./routes/environments/environment-variables.tsx"
            ),
            route("settings", "./routes/environments/environments-settings.tsx")
          ]),

          ...prefix("create-service", [
            route("", "./routes/services/create-service.tsx"),
            route("docker", "./routes/services/create-docker-service.tsx"),
            route(
              "git-public",
              "./routes/services/create-public-git-service.tsx"
            ),
            route(
              "git-private",
              "./routes/services/create-private-git-service.tsx"
            ),
            route(
              "git-private/:gitAppId",
              "./routes/services/create-git-service-from-gitapp.tsx"
            )
          ]),

          ...prefix("services/:serviceSlug", [
            route("", "./routes/layouts/service-layout.tsx", [
              index("./routes/services/services-deployment-list.tsx"),
              route(
                "env-variables",
                "./routes/services/services-env-variables.tsx"
              ),
              route(
                "settings",
                "./routes/services/settings/service-settings.tsx"
              ),
              route("http-logs", "./routes/services/service-http-logs.tsx"),
              route("metrics", "./routes/services/service-metrics.tsx")
            ]),

            route(
              "deployments/:deploymentHash",
              "./routes/layouts/deployment-layout.tsx",
              [
                index("./routes/deployments/deployment-logs.tsx"),
                route("details", "./routes/deployments/deployment-details.tsx"),
                route(
                  "terminal",
                  "./routes/deployments/deployment-terminal.tsx"
                ),
                route(
                  "http-logs",
                  "./routes/deployments/deployment-http-logs.tsx"
                ),
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
          ]),

          ...prefix("create-compose-stack", [
            route("", "./routes/compose/create-compose-stack.tsx"),
            route(
              "compose-contents",
              "./routes/compose/create-compose-stack-from-contents.tsx"
            ),
            route(
              "dokploy",
              "./routes/compose/create-compose-stack-from-dokploy.tsx"
            ),
            route(
              "template",
              "./routes/compose/compose-stack-template-list.tsx"
            ),
            route(
              "template/:templateSlug",
              "./routes/compose/create-compose-stack-from-template.tsx"
            )
          ]),

          ...prefix("compose-stacks/:composeStackSlug", [
            route("", "./routes/layouts/compose-stack-layout.tsx", [
              index("./routes/compose/compose-stack-service-list.tsx"),
              route("settings", "./routes/compose/compose-stack-settings.tsx"),
              route("deploy", "./routes/compose/deploy-compose-stack.tsx"),
              route("toggle", "./routes/compose/toggle-compose-stack.tsx"),
              route("archive", "./routes/compose/archive-compose-stack.tsx"),
              route(
                "regenerate-token",
                "./routes/compose/regenerate-compose-stack-deploy-token.tsx"
              ),
              route(
                "http-logs",
                "./routes/compose/compose-stack-http-logs.tsx"
              ),
              route("metrics", "./routes/compose/compose-stack-metrics.tsx"),
              route(
                "deployments",
                "./routes/compose/compose-stack-deployment-list.tsx"
              ),
              route(
                "discard-multiple-changes",
                "./routes/compose/discard-compose-stack-multiple-changes.tsx"
              ),
              route(
                "discard-change",
                "./routes/compose/discard-compose-stack-change.tsx"
              )
            ]),

            route(
              "services/:serviceSlug",
              "./routes/layouts/compose-stack-service-layout.tsx",
              [
                index("./routes/compose/compose-stack-service-replicas.tsx"),
                route(
                  "runtime-logs",
                  "./routes/compose/compose-stack-service-runtime-logs.tsx"
                ),
                route(
                  "terminal",
                  "./routes/compose/compose-stack-service-terminal.tsx"
                ),
                route(
                  "http-logs",
                  "./routes/compose/compose-stack-service-http-logs.tsx"
                ),
                route(
                  "metrics",
                  "./routes/compose/compose-stack-service-metrics.tsx"
                ),
                route(
                  "details",
                  "./routes/compose/compose-stack-service-details.tsx"
                )
              ]
            ),

            route(
              "deployments/:deploymentHash",
              "./routes/layouts/compose-stack-deployment-layout.tsx",
              [
                index("./routes/compose/compose-stack-deployment-logs.tsx"),
                route(
                  "details",
                  "./routes/compose/compose-stack-deployment-details.tsx"
                ),
                route(
                  "cancel",
                  "./routes/compose/cancel-compose-deployment.tsx"
                ),
                route(
                  "redeploy",
                  "./routes/compose/redeploy-compose-deployment.tsx"
                )
              ]
            )
          ])
        ])
      ])
    ])
  ])
] satisfies RouteConfig;
