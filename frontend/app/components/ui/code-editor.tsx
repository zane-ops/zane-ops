import MonacoEditor, {
  type EditorProps,
  DiffEditor as MonacoDiffEditor,
  type DiffEditorProps
} from "@monaco-editor/react";
import { useMediaQuery } from "@uidotdev/usehooks";
import { Maximize2Icon, Minimize2Icon } from "lucide-react";
import * as React from "react";
import { useTheme } from "~/components/theme-provider";
import { Button } from "~/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { cn } from "~/lib/utils";

export type CodeEditorProps = {
  value?: string;
  language?: string;
  readOnly?: boolean;
  onChange?: (value: string | undefined) => void;
  className?: string;
  containerClassName?: string;
  fontSize?: number;
  hasError?: boolean;
} & Pick<EditorProps, "options">;

export function CodeEditor({
  value,
  language,
  readOnly = false,
  onChange,
  className,
  containerClassName,
  fontSize,
  options,
  hasError
}: CodeEditorProps) {
  const { theme } = useTheme();
  const isDark = useMediaQuery("(prefers-color-scheme: dark)");
  const resolvedTheme =
    theme === "SYSTEM" ? (isDark ? "DARK" : "LIGHT") : theme;
  const editorTheme = resolvedTheme === "LIGHT" ? "vs-light" : "vs-dark";

  const [isFullScreen, setIsFullScreen] = React.useState(false);

  const isDev = !import.meta.env.PROD;

  return (
    <div
      className={cn(
        "resize-y h-52 min-h-52 overflow-y-auto overflow-x-clip max-w-full",
        "border border-border",
        "ring-offset-background focus-within:ring-2 focus-within:ring-ring/60 focus-within:ring-offset-2 outline-hidden",
        "group",
        hasError && "border-red-500 focus-within:ring-red-500/50",
        isFullScreen
          ? "fixed z-90 inset-0 !w-dvw !h-dvh !max-w-dvw !max-h-dvh"
          : "relative w-fit max-w-full",
        isDev && isFullScreen && "top-7",
        containerClassName
      )}
    >
      <TooltipProvider>
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <Button
              variant="outline"
              className="absolute top-4 right-4 z-30"
              onClick={() => {
                setIsFullScreen((prev) => !prev);
              }}
            >
              <span className="sr-only">
                {isFullScreen ? "Exit full screen" : "Enter full screen"}
              </span>
              {isFullScreen ? (
                <Minimize2Icon className="size-4 flex-none" />
              ) : (
                <Maximize2Icon className="size-4 flex-none" />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent className="max-w-64 text-balance">
            {isFullScreen ? "Exit full screen" : "Enter full screen"}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <MonacoEditor
        className={cn("w-full h-full max-w-full", className)}
        language={language}
        value={value}
        theme={editorTheme}
        options={{
          readOnly,
          fontSize,
          minimap: {
            enabled: false
          },
          ...options
        }}
        onChange={onChange}
      />
    </div>
  );
}

export type DiffCodeEditorProps = {
  original: string;
  modified?: string;
  language?: string;
  readOnly?: boolean;
  className?: string;
  containerClassName?: string;
  fontSize?: number;
  hasError?: boolean;
} & Pick<DiffEditorProps, "options">;

export function DiffCodeEditor({
  original,
  modified,
  language,
  readOnly = false,
  className,
  containerClassName,
  fontSize,
  options,
  hasError
}: DiffCodeEditorProps) {
  const { theme } = useTheme();
  const isDark = useMediaQuery("(prefers-color-scheme: dark)");
  const resolvedTheme =
    theme === "SYSTEM" ? (isDark ? "DARK" : "LIGHT") : theme;
  const editorTheme = resolvedTheme === "LIGHT" ? "vs-light" : "vs-dark";

  const [isFullScreen, setIsFullScreen] = React.useState(false);

  const isDev = !import.meta.env.PROD;

  return (
    <div
      className={cn(
        "resize-y h-52 min-h-52 overflow-y-auto overflow-x-clip max-w-full",
        "border border-border",
        "ring-offset-background focus-within:ring-2 focus-within:ring-ring/60 focus-within:ring-offset-2 outline-hidden",
        "group",
        hasError && "border-red-500 focus-within:ring-red-500/50",
        isFullScreen
          ? "fixed z-90 inset-0 !w-dvw !h-dvh !max-w-dvw !max-h-dvh"
          : "relative w-fit max-w-full",
        isDev && isFullScreen && "top-7",
        containerClassName
      )}
    >
      <TooltipProvider>
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <Button
              variant="outline"
              className="absolute top-4 right-4 z-30"
              onClick={() => {
                setIsFullScreen((prev) => !prev);
              }}
            >
              <span className="sr-only">
                {isFullScreen ? "Exit full screen" : "Enter full screen"}
              </span>
              {isFullScreen ? (
                <Minimize2Icon className="size-4 flex-none" />
              ) : (
                <Maximize2Icon className="size-4 flex-none" />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent className="max-w-64 text-balance">
            {isFullScreen ? "Exit full screen" : "Enter full screen"}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <MonacoDiffEditor
        className={cn("w-full h-full max-w-full", className)}
        language={language}
        modified={modified}
        original={original}
        theme={editorTheme}
        options={{
          readOnly,
          fontSize,
          minimap: {
            enabled: false
          },
          ...options
        }}
      />
    </div>
  );
}
