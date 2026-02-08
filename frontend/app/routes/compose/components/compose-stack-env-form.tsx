import { ExternalLinkIcon } from "lucide-react";
import type { ComposeStack } from "~/api/types";
import { Code } from "~/components/code";

export type ComposeStackEnvFormProps = {
  stack: ComposeStack;
};

type EnvVariableUI = {
  change_id?: string;
  id?: string | null;
  key: string;
  value: string;
  change_type?: "UPDATE" | "DELETE" | "ADD";
};

export function ComposeStackEnvForm({ stack }: ComposeStackEnvFormProps) {
  const env_variables: Map<string, EnvVariableUI> = new Map();
  for (const env of stack?.env_overrides ?? []) {
    env_variables.set(env.id, {
      id: env.id,
      key: env.key,
      value: env.value
    });
  }
  for (const ch of stack.unapplied_changes.filter(
    (ch) => ch.field === "env_overrides"
  )) {
    const keyValue = (ch.new_value ?? ch.old_value) as {
      key: string;
      value: string;
    };
    env_variables.set(ch.item_id ?? ch.id, {
      change_id: ch.id,
      id: ch.item_id,
      key: keyValue.key,
      value: keyValue.value,
      change_type: ch.type
    });
  }
  return (
    <div className="w-full max-w-4xl flex flex-col gap-5">
      <p className="text-gray-400">
        Override environment variables declared in the{" "}
        <Code className="text-sm">x-zane-env</Code> section of your
        docker-compose.yml. More info in{" "}
        <a
          href="#"
          target="_blank"
          className="text-link underline inline-flex gap-1"
        >
          the docs <ExternalLinkIcon className="size-4 flex-none" />
        </a>
      </p>

      <section className="flex flex-col gap-4">
        {env_variables.size > 0 && (
          <>
            <ul className="flex flex-col gap-1">
              {[...env_variables.entries()].map(([, env]) => (
                <li key={env.key}>
                  {/* <EnVariableRow
                          name={env.name}
                          value={env.value}
                          id={env.id}
                          change_id={env.change_id}
                          change_type={env.change_type}
                        /> */}
                </li>
              ))}
            </ul>
            <hr className="border-border" />
          </>
        )}
        <h3 className="text-lg">Add new variable</h3>
        <p className="text-grey">
          Use <Code>{"{{env.VARIABLE_NAME}}"}</Code> to reference variables in
          the parent environment
        </p>
        {/* <NewEnvVariableForm /> */}
      </section>
    </div>
  );
}
