import {
  ChevronRightIcon,
  ExternalLinkIcon,
  PencilLineIcon,
  PlusIcon
} from "lucide-react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
import { Button } from "~/components/ui/button";
import { Input } from "~/components/ui/input";
import { cn } from "~/lib/utils";
import type { Route } from "./+types/project-environments";

export default function EnvironmentsPage({
  matches: {
    "2": {
      data: { project }
    }
  }
}: Route.ComponentProps) {
  const environments = project.environments;
  return (
    <div className="grid lg:grid-cols-12">
      <div className="my-4 flex flex-col items-start gap-2 lg:col-span-10">
        <h2 className="text-xl font-medium">List of environments</h2>
        <p className="text-grey">
          Each environment provides a separate instance of each service.&nbsp;
          <a
            href="#"
            target="_blank"
            className="text-link underline inline-flex gap-1 items-center"
          >
            Read the docs <ExternalLinkIcon size={12} />
          </a>
        </p>

        <div className="flex flex-col gap-4 w-full">
          {environments.map((env, index) => (
            <section key={env.id} className="flex flex-col gap-4">
              <fieldset className="flex flex-col gap-1.5 flex-1 w-full">
                <label htmlFor={`env-${env.id}`} className="sr-only">
                  name
                </label>
                <div className="relative">
                  <Input
                    id={`env-${env.id}`}
                    name="name"
                    // ref={inputRef}
                    placeholder="ex: staging"
                    defaultValue={env.name}
                    // disabled={!isEditing}
                    disabled
                    aria-labelledby="slug-error"
                    // aria-invalid={Boolean(errors.slug)}
                    className={cn(
                      "disabled:placeholder-shown:font-mono disabled:bg-muted",
                      "disabled:border-transparent disabled:opacity-100"
                    )}
                  />

                  {/* {!isEditing && ( */}
                  <Button
                    variant="outline"
                    onClick={() => {
                      // flushSync(() => {
                      //   setIsEditing(true);
                      // });
                      // inputRef.current?.focus();
                    }}
                    className={cn(
                      "absolute inset-y-0 right-0 text-sm py-0 border-0",
                      "bg-inherit inline-flex items-center gap-2 border-muted-foreground py-0.5"
                    )}
                  >
                    <span>Edit</span>
                    <PencilLineIcon size={15} />
                  </Button>
                  {/* )} */}
                </div>

                {/* {errors.slug && (
            <span id="slug-error" className="text-red-500 text-sm">
              {errors.slug}
            </span>
          )} */}
              </fieldset>

              {/* <Accordion
              type="single"
              collapsible
              className="border-t border-border"
            >
              <AccordionItem value="system">
                <AccordionTrigger className="text-muted-foreground font-normal text-sm hover:underline">
                  <ChevronRightIcon className="h-4 w-4 shrink-0 transition-transform duration-200" />
                  No env specific variables
                </AccordionTrigger>
              </AccordionItem>
            </Accordion> */}

              {index < environments.length - 1 && (
                <hr className="border border-dashed border-border" />
              )}
            </section>
          ))}

          <Button className="inline-flex gap-1 items-center self-start">
            <PlusIcon size={15} />
            New Environment
          </Button>
        </div>
      </div>
    </div>
  );
}
