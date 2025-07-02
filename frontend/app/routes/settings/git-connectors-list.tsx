import {
  ChevronDownIcon,
  GithubIcon,
  GitlabIcon,
  PlusIcon
} from "lucide-react";
import { Link, href, useNavigate } from "react-router";
import { Button } from "~/components/ui/button";
import {
  Menubar,
  MenubarContent,
  MenubarContentItem,
  MenubarMenu,
  MenubarTrigger
} from "~/components/ui/menubar";
import { Separator } from "~/components/ui/separator";
import { metaTitle } from "~/utils";
import type { Route } from "./+types/git-connectors-list";

export function meta() {
  return [metaTitle("Git apps")] satisfies ReturnType<Route.MetaFunction>;
}

export default function GitConnectorsListPage({}: Route.ComponentProps) {
  const navigate = useNavigate();
  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-2xl">Git apps</h2>
        <Menubar className="border-none md:block hidden w-fit">
          <MenubarMenu>
            <MenubarTrigger asChild>
              <Button variant="secondary" className="flex gap-2">
                Create <ChevronDownIcon size={18} />
              </Button>
            </MenubarTrigger>
            <MenubarContent
              align="center"
              alignOffset={0}
              className="border min-w-0 mx-9  border-border"
            >
              <MenubarContentItem
                icon={GithubIcon}
                text="GitHub app"
                onClick={() => {
                  navigate(href("/settings/git-connectors/create-github-app"));
                }}
              />

              <MenubarContentItem
                icon={GitlabIcon}
                text="gitlab app"
                disabled
                // onClick={() => {
                //   navigate("/settings");
                // }}
              />
            </MenubarContent>
          </MenubarMenu>
        </Menubar>
      </div>
      <Separator />
      <h3>
        Connect your Git provider to deploy private repositories, auto-deploy on
        commit as well as create pull request preview environments.
      </h3>

      <ul className="flex flex-col gap-2">
        <div className="border-border border-dashed border-1 flex items-center justify-center px-6 py-10 text-grey">
          No connector found
        </div>
        {/* {sshKeys.length === 0 ? (
          <div className="border-border border-dashed border-1 flex items-center justify-center p-6 text-grey">
            No SSH Key found
          </div>
        ) : (
          sshKeys.map((ssh_key) => (
            <li key={ssh_key.id}>
              <SSHKeyCard ssh_key={ssh_key} />
            </li>
          ))
        )} */}
      </ul>
    </section>
  );
}
