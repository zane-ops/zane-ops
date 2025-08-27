import {
  ContainerIcon,
  GitBranchIcon,
  GithubIcon,
  GitlabIcon,
  HardDrive,
  LinkIcon,
  Tag
} from "lucide-react";
import * as React from "react";
import { Link } from "react-router";
import { Checkbox } from "~/components/ui/checkbox";
import { cn } from "~/lib/utils";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle
} from "./ui/card";
import { Separator } from "./ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "./ui/tooltip";

type CommonServiceCardProps = {
  slug: string;
  status:
    | "HEALTHY"
    | "UNHEALTHY"
    | "SLEEPING"
    | "NOT_DEPLOYED_YET"
    | "DEPLOYING"
    | "FAILED"
    | "CANCELLED";
  volumeNumber?: number;
  url?: string | null;
  updatedAt: string;
  id: string;
  selected?: boolean;
  onToggleSelect?: (serviceId: string) => void;
};

type DockerServiceCardProps = CommonServiceCardProps & {
  image: string;
  tag: string;
};

export function DockerServiceCard({
  slug,
  image,
  url,
  tag,
  updatedAt,
  volumeNumber = 0,
  status,
  id,
  selected,
  onToggleSelect
}: DockerServiceCardProps) {
  let avatarSrc: string | null = null;

  const imageWithoutTag = image.split(":")[0];
  let isDockerHubImage =
    !imageWithoutTag.startsWith("ghcr.io") && !imageWithoutTag.includes(".");

  const [imageNotFound, setImageNotFound] = React.useState(false);

  if (imageWithoutTag.startsWith("ghcr.io")) {
    // GitHub Container Registry: use GitHub username as avatar
    const fullImage = imageWithoutTag.split("/");
    const username = fullImage[1];
    avatarSrc = `https://github.com/${username}.png`;
  } else if (isDockerHubImage) {
    avatarSrc = `https://zaneops.dev/icons?image=${imageWithoutTag}`;
  }
  // Other registries are ignored

  return (
    <Card className="rounded-2xl flex group flex-col h-[220px] bg-toggle relative ring-1 ring-transparent hover:ring-primary focus-within:ring-primary transition-colors duration-300">
      <TooltipProvider>
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <span
              tabIndex={0}
              className="absolute cursor-pointer flex h-4 w-4 -top-1 -right-1 z-10"
            >
              {status !== "NOT_DEPLOYED_YET" && status !== "CANCELLED" && (
                <span
                  className={cn(
                    "animate-ping absolute inline-flex h-full w-full rounded-full  opacity-75",
                    {
                      "bg-green-400": status === "HEALTHY",
                      "bg-red-400":
                        status === "UNHEALTHY" || status === "FAILED",
                      "bg-yellow-400": status === "SLEEPING",
                      "bg-secondary/60": status === "DEPLOYING"
                    }
                  )}
                />
              )}

              <span
                className={cn(
                  "relative inline-flex rounded-full h-4 w-4 bg-green-500",
                  {
                    "bg-green-500": status === "HEALTHY",
                    "bg-red-500": status === "UNHEALTHY" || status === "FAILED",
                    "bg-yellow-500": status === "SLEEPING",
                    "bg-gray-400":
                      status === "NOT_DEPLOYED_YET" || status === "CANCELLED",
                    "bg-secondary": status === "DEPLOYING"
                  }
                )}
              ></span>
              <span className="sr-only">{status}</span>
            </span>
          </TooltipTrigger>
          <TooltipContent>
            <div>
              {status === "HEALTHY" && "✅ Healthy"}
              {status === "SLEEPING" && "🌙 Sleeping"}
              {status === "UNHEALTHY" && "❌ Unhealthy"}
              {status === "FAILED" && "❌ Failed"}
              {status === "DEPLOYING" && "⏳ Deploying..."}
              {status === "CANCELLED" && "🚫 Cancelled"}
              {status === "NOT_DEPLOYED_YET" && "🚧 Not deployed yet"}
            </div>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <CardHeader className="p-0  pb-0  pt-4 px-6">
        <CardTitle className="flex gap-2 items-center">
          {avatarSrc && !imageNotFound ? (
            <img
              src={avatarSrc}
              onError={() => setImageNotFound(true)}
              alt={`Logo for ${image}`}
              className={cn(
                "size-8 flex-none object-center object-contain",
                "rounded-md border border-border p-0.5"
              )}
            />
          ) : (
            <ContainerIcon
              className={cn(
                "flex-none",
                "rounded-md border border-border p-0.5"
              )}
              size={32}
            />
          )}
          <div className="w-[calc(100%-38px)]">
            <h2 className="text-lg leading-tight">
              <Link
                to={`services/${slug}`}
                prefetch="viewport"
                className="hover:underline after:inset-0 after:absolute"
              >
                {slug}
              </Link>
            </h2>
            <p className="text-sm font-normal overflow-x-hidden text-ellipsis whitespace-nowrap text-gray-400 leading-tight relative z-10">
              {image}
            </p>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex  justify-end grow gap-0.5 flex-col text-sm text-gray-400 p-6">
        {!!url && (
          <a
            href={`//${url}`}
            target="_blank"
            className="text-sm flex items-center gap-2 text-link z-10 relative hover:underline"
          >
            <LinkIcon className="flex-none" size={15} />
            <div className="whitespace-nowrap overflow-x-hidden text-ellipsis">
              {url}
            </div>
          </a>
        )}

        <p className="flex items-center gap-2 z-10 relative text-ellipsis overflow-x-hidden whitespace-nowrap">
          <Tag size={15} /> <span>{tag}</span>
        </p>
        <p className="flex gap-2 items-center z-10 relative">{updatedAt}</p>
      </CardContent>

      <Separator />
      <CardFooter className="p-0 text-gray-400 px-6 py-4 text-sm flex gap-2">
        <HardDrive size={20} />
        {volumeNumber > 0 ? (
          <span>
            {volumeNumber}
            {volumeNumber > 1 ? " Volumes" : " Volume"}
          </span>
        ) : (
          <>No Volume attached</>
        )}
      </CardFooter>
      <label
        htmlFor={`select-${slug}`}
        className="absolute bottom-2 right-2 p-2 z-10 flex items-center justify-center"
      >
        <Checkbox
          id={`select-${slug}`}
          checked={selected}
          onCheckedChange={() => onToggleSelect?.(id)}
          className="opacity-100 md:opacity-0 group-focus-within:opacity-100 data-[state=checked]:opacity-100 group-hover:opacity-100"
        />
      </label>
    </Card>
  );
}

type GitServiceCardProps = CommonServiceCardProps & {
  repository: string;
  lastCommitMessage?: string | null;
  branchName: string;
  git_provider?: "github" | "gitlab" | "" | null;
};

export function GitServiceCard({
  slug,
  repository,
  url,
  updatedAt,
  lastCommitMessage,
  volumeNumber = 0,
  branchName,
  status,
  id,
  selected,
  onToggleSelect,
  git_provider
}: GitServiceCardProps) {
  return (
    <Card className="rounded-2xl group flex flex-col h-[220px] bg-toggle relative ring-1 ring-transparent hover:ring-primary focus-within:ring-primary transition-colors duration-300">
      <TooltipProvider>
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <span className="absolute cursor-pointer flex h-4 w-4 -top-1 -right-1 z-10">
              {status !== "NOT_DEPLOYED_YET" && status !== "CANCELLED" && (
                <span
                  className={cn(
                    "animate-ping absolute inline-flex h-full w-full rounded-full  opacity-75",
                    {
                      "bg-green-400": status === "HEALTHY",
                      "bg-red-500":
                        status === "UNHEALTHY" || status === "FAILED",
                      "bg-yellow-400": status === "SLEEPING",
                      "bg-secondary/60": status === "DEPLOYING"
                    }
                  )}
                />
              )}

              <span
                className={cn(
                  "relative inline-flex rounded-full h-4 w-4 bg-green-500",
                  {
                    "bg-green-500": status === "HEALTHY",
                    "bg-red-500": status === "UNHEALTHY" || status === "FAILED",
                    "bg-yellow-500": status === "SLEEPING",
                    "bg-gray-400":
                      status === "NOT_DEPLOYED_YET" || status === "CANCELLED",
                    "bg-secondary": status === "DEPLOYING"
                  }
                )}
              ></span>
            </span>
          </TooltipTrigger>
          <TooltipContent>
            <div>
              {status === "HEALTHY" && "✅ Healthy"}
              {status === "FAILED" && "❌ Failed"}
              {status === "SLEEPING" && "🌙 Sleeping"}
              {status === "UNHEALTHY" && "❌ Unhealthy"}
              {status === "DEPLOYING" && "⏳ Deploying..."}
              {status === "CANCELLED" && "🚫 Cancelled"}
              {status === "NOT_DEPLOYED_YET" && "🚧 Not deployed yet"}
            </div>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <CardHeader className="p-0  pb-0  pt-4 px-6">
        <CardTitle className="flex gap-2 items-center">
          {repository?.startsWith("https://gitlab.com") ||
          git_provider === "gitlab" ? (
            <GitlabIcon size={32} className={cn("flex-none")} />
          ) : (
            <GithubIcon className={cn("flex-none")} size={32} />
          )}
          <div className="w-[calc(100%-38px)]">
            <h2 className="text-lg leading-tight">
              <Link
                to={`services/${slug}`}
                prefetch="viewport"
                className="hover:underline after:inset-0 after:absolute"
              >
                {slug}
              </Link>
            </h2>
            <p
              className={cn(
                "font-normal overflow-x-hidden text-ellipsis whitespace-nowrap",
                "text-gray-400 leading-tight text-sm hover:underline"
              )}
            >
              {repository}
            </p>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex  justify-end grow gap-0.5 flex-col text-sm text-gray-400 p-6">
        {!!url && (
          <a
            href={`//${url}`}
            target="_blank"
            className="text-sm flex items-center gap-2 text-link relative z-10 hover:underline"
          >
            <LinkIcon className="flex-none" size={15} />
            <div className="whitespace-nowrap overflow-x-hidden  text-ellipsis ">
              {url}
            </div>
          </a>
        )}

        <p className="text-ellipsis overflow-x-hidden whitespace-nowrap relative z-10">
          {lastCommitMessage}
        </p>
        <div className="flex gap-2 items-center relative z-10">
          <p className="min-w-fit">
            {updatedAt}&nbsp;{lastCommitMessage && "on"}
          </p>
          {lastCommitMessage && (
            <>
              <GitBranchIcon size={15} />
              <p className="text-ellipsis overflow-x-hidden whitespace-nowrap relative z-10">
                {branchName}
              </p>
            </>
          )}
        </div>
      </CardContent>
      <Separator />
      <CardFooter className="p-0 text-gray-400 px-6 py-4 text-sm flex gap-2">
        <HardDrive size={20} />
        {volumeNumber > 0 ? (
          <span>
            {volumeNumber}
            {volumeNumber > 1 ? " Volumes" : " Volume"}
          </span>
        ) : (
          <>No Volume attached</>
        )}
      </CardFooter>
      <label
        htmlFor={`select-${slug}`}
        className="absolute bottom-2 right-2 p-2 z-10 flex items-center justify-center"
      >
        <Checkbox
          id={`select-${slug}`}
          checked={selected}
          onCheckedChange={() => onToggleSelect?.(id)}
          className="opacity-100 md:opacity-0 group-focus-within:opacity-100 data-[state=checked]:opacity-100 group-hover:opacity-100"
        />
      </label>
    </Card>
  );
}
