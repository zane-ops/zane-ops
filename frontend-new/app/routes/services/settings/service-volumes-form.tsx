import {
  AlertCircleIcon,
  ArrowRightIcon,
  CheckIcon,
  CopyIcon,
  InfoIcon,
  LoaderIcon,
  Plus,
  Trash2Icon,
  Undo2Icon
} from "lucide-react";
import * as React from "react";
import { Code } from "~/components/code";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
import { Checkbox } from "~/components/ui/checkbox";
import {
  FieldSet,
  FieldSetCheckbox,
  FieldSetErrors,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { type DockerService } from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import {
  type clientAction,
  useFetcherWithCallbacks,
  useServiceQuery
} from "~/routes/services/settings/services-settings";

export type ServiceVolumesFormProps = {
  project_slug: string;
  service_slug: string;
};

export function ServiceVolumesForm({
  project_slug,
  service_slug
}: ServiceVolumesFormProps) {
  const { data: service } = useServiceQuery({ project_slug, service_slug });

  return <></>;
}
