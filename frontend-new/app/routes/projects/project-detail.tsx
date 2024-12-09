import { metaTitle } from "~/utils";
import { type Route } from "./+types/project-detail";

export const meta: Route.MetaFunction = ({ params }) => {
  return [metaTitle(`Project Detail`)];
};
export default function ProjectDetail() {
  return <></>;
}
