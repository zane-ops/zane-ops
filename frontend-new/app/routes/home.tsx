import type { Route } from "./+types/home";

export function meta({}: Route.MetaArgs) {
  return [{ title: "Dashboard | ZaneOps" }];
}

export default function Home() {
  return <h1 className="text-2xl">Welcome to ZaneOps</h1>;
}
