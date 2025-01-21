import { type Route } from "./+types/service-http-logs";

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  return {};
}

export default function ServiceHttpLogsPage({}: Route.ComponentProps) {
  return <>service-http-logs Page</>;
}
