import MonacoEditor, { type EditorProps } from "@monaco-editor/react";
import { useMediaQuery } from "@uidotdev/usehooks";
import { useTheme } from "~/components/theme-provider";
import { cn } from "~/lib/utils";

export type CodeEditorProps = {
  value?: string;
  language?: string;
  readOnly?: boolean;
  onChange?: (value: string | undefined) => void;
  className?: string;
  containerClassName?: string;
  fontSize?: number;
} & Pick<EditorProps, "options">;

export function CodeEditor({
  value,
  language,
  readOnly = false,
  onChange,
  className,
  containerClassName,
  fontSize,
  options
}: CodeEditorProps) {
  const { theme } = useTheme();
  const isDark = useMediaQuery("(prefers-color-scheme: dark)");
  const resolvedTheme =
    theme === "SYSTEM" ? (isDark ? "DARK" : "LIGHT") : theme;
  const editorTheme = resolvedTheme === "LIGHT" ? "vs-light" : "vs-dark";

  return (
    <div
      className={cn(
        "resize-y h-52 min-h-52 overflow-y-auto overflow-x-clip max-w-full",
        containerClassName
      )}
    >
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
