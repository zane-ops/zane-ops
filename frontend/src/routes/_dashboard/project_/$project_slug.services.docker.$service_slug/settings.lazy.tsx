import { createLazyFileRoute } from '@tanstack/react-router'

export const Route = createLazyFileRoute('/_dashboard/project/$project_slug/services/docker/$service_slug/settings')({
  component: () => <div>Hello /_dashboard/project/$project_slug/services/docker/$service_slug/settings!</div>
})