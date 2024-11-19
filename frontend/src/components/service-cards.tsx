import { Link } from "@tanstack/react-router";
import {
  Container,
  GitBranchIcon,
  Github,
  HardDrive,
  LinkIcon,
  Tag
} from "lucide-react";
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
    | "CANCELLED";
  volumeNumber?: number;
  url?: string | null;
  updatedAt: string;
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
  status
}: DockerServiceCardProps) {
  return (
    <Card className="rounded-2xl flex flex-col h-[220px] bg-toggle relative ring-1 ring-transparent hover:ring-primary focus-within:ring-primary transition-colors duration-300">
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
                      "bg-red-400": status === "UNHEALTHY",
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
                    "bg-red-500": status === "UNHEALTHY",
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
              {status === "DEPLOYING" && "⏳ Deploying..."}
              {status === "CANCELLED" && "🚫 Cancelled"}
              {status === "NOT_DEPLOYED_YET" && "🚧 Not deployed yet"}
            </div>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <CardHeader className="p-0  pb-0  pt-4 px-6">
        <CardTitle className="flex gap-2 items-center">
          <Container className="flex-none" size={30} />
          <div className="w-[calc(100%-38px)]">
            <h2 className="text-lg leading-tight">
              <Link
                to={`services/docker/${slug}`}
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
      <CardContent className="flex  justify-end flex-grow gap-0.5 flex-col text-sm text-gray-400 p-6">
        {!!url && (
          <a
            href={`//${url}`}
            target="_blank"
            className="text-sm flex items-center gap-2 text-link z-10 relative hover:underline"
          >
            <LinkIcon className="flex-none" size={15} />
            <div className="whitespace-nowrap overflow-x-hidden  text-ellipsis ">
              {url}
            </div>
          </a>
        )}

        <p className="flex items-center gap-2 z-10 relative">
          <Tag size={15} /> {tag}
        </p>
        <p className="flex gap-2 items-center z-10 relative">{updatedAt}</p>
      </CardContent>

      <Separator />
      <CardFooter className="p-0 text-gray-400 px-6 py-4 text-sm flex gap-2">
        <HardDrive size={20} /> {volumeNumber}
        {volumeNumber > 1 ? " Volumes" : " Volume"}
      </CardFooter>
    </Card>
  );
}

type GitServiceCardProps = CommonServiceCardProps & {
  repository: string;
  lastCommitMessage?: string;
  branchName: string;
};

export function GitServiceCard({
  slug,
  repository,
  url,
  updatedAt,
  lastCommitMessage,
  volumeNumber = 0,
  branchName,
  status
}: GitServiceCardProps) {
  return (
    <Card className="rounded-2xl bg-toggle relative ring-1 ring-transparent hover:ring-primary focus-within:ring-primary transition-colors duration-300">
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
                      "bg-red-400": status === "UNHEALTHY",
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
                    "bg-red-500": status === "UNHEALTHY",
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
          <Github className="flex-none" size={30} />
          <div className="w-[calc(100%-38px)]">
            <h2 className="text-lg leading-tight">
              <Link
                to={`services/git/${slug}`}
                className="hover:underline after:inset-0 after:absolute"
              >
                {slug}
              </Link>
            </h2>
            <p className="text-sm font-medium overflow-x-hidden text-ellipsis whitespace-nowrap text-gray-400 leading-tight hover:underline">
              {repository}
            </p>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex  gap-0.5 flex-col text-sm text-gray-400 p-0 px-6 py-6">
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
        <p className="flex gap-2 items-center relative z-10">
          {updatedAt} on <GitBranchIcon size={15} /> {branchName}
        </p>
      </CardContent>
      <Separator />
      <CardFooter className="p-0 text-gray-400 px-6 py-3 text-sm flex gap-2">
        <HardDrive size={20} /> {volumeNumber}
        {volumeNumber > 1 ? " Volumes" : " Volume"}
      </CardFooter>
    </Card>
  );
}
