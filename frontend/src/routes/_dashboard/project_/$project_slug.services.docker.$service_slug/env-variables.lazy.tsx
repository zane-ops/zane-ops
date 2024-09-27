import { createLazyFileRoute } from '@tanstack/react-router'

export const Route = createLazyFileRoute('/_dashboard/project/$project_slug/services/docker/$service_slug/env-variables')({
  component: () => <div>Hello /_dashboard/project/$project_slug/services/docker/$service_slug/env-variables!</div>
})