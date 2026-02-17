import { AnsiHtml } from "fancy-ansi/react";
import { ChevronRightIcon, ChevronsUpDownIcon, FilterIcon } from "lucide-react";
import * as React from "react";
import { useSearchParams } from "react-router";
import { buttonVariants } from "~/components/ui/button";
import { MAX_VISIBLE_LOG_CHARS_LIMIT } from "~/lib/constants";
import type { DeploymentLog } from "~/lib/queries";
import { cn, formatLogTime } from "~/lib/utils";
import { excerpt, stringToColor } from "~/utils";

type LogProps = Pick<DeploymentLog, "id" | "level" | "time" | "timestamp"> & {
  content: string;
  content_text: string;
  container_id?: string | null;
};

export function Log({
  content,
  level,
  time,
  timestamp,
  id,
  content_text,
  container_id
}: LogProps) {
  const date = new Date(time);

  const [searchParams, setSearchParams] = useSearchParams();
  const search = searchParams.get("query") ?? "";

  const logTime = formatLogTime(date);

  const isSelectedContext =
    searchParams.get("context") === timestamp.toString();

  const shortContainerId = container_id?.substring(0, 12);
  const containerColor = stringToColor(container_id ?? "");

  return (
    <div
      id={`log-item-${id}`}
      className={cn(
        "w-full flex gap-2 hover:bg-slate-400/20 relative group",
        "py-0 px-4 border-none border-0 ring-0",
        level === "ERROR" && "bg-red-400/20",
        isSelectedContext && "bg-yellow-400/20"
      )}
    >
      {isSelectedContext && (
        <div className="w-0.5 bg-yellow-400 absolute top-0 bottom-0 left-0" />
      )}

      <span className="inline-flex items-start select-none min-w-fit flex-none relative ">
        <time className="text-grey" dateTime={date.toISOString()}>
          <span className="sr-only sm:not-sr-only">
            {logTime.dateFormat},&nbsp;
          </span>
          <span>{logTime.hourFormat}</span>
        </time>

        {searchParams.get("query") && (
          <button
            onClick={() => {
              searchParams.set("context", timestamp.toString());
              setSearchParams(searchParams);
            }}
            className={cn(
              buttonVariants({
                variant: "outline"
              }),
              "starting:h-0 starting:scale-90",
              "absolute bottom-full -left-4 hidden group-hover:inline-flex z-10",
              "px-2 py-1 mx-2 h-auto rounded items-center cursor-pointer gap-1",
              "transition-all duration-150 text-xs"
            )}
          >
            <span className="">View in context</span>
            <ChevronsUpDownIcon
              className={cn("flex-none relative top-0.25")}
              size={12}
            />
          </button>
        )}
      </span>

      {container_id && (
        <div
          className="whitespace-nowrap relative group/replica"
          style={
            {
              "--container-color-light": containerColor.light,
              "--container-color-dark": containerColor.dark
            } as React.CSSProperties
          }
        >
          <span className="text-[var(--container-color-light)] dark:text-[var(--container-color-dark)]">
            &nbsp;|&nbsp;{shortContainerId}&nbsp;|
          </span>

          <button
            onClick={() => {
              searchParams.set("container_id", container_id.toString());
              setSearchParams(searchParams);
            }}
            className={cn(
              buttonVariants({
                variant: "outline"
              }),
              "starting:h-0 starting:scale-90",
              "absolute bottom-full -left-4 hidden group-hover/replica:inline-flex z-10",
              "px-2 py-1 mx-2 h-auto rounded items-center cursor-pointer gap-1",
              "transition-all duration-150 text-xs"
            )}
          >
            <span className="">Filter by replica</span>
            <FilterIcon
              className={cn("flex-none relative top-0.25")}
              size={12}
            />
          </button>
        </div>
      )}

      <div className="grid relative z-10 w-full">
        {content_text.length <= MAX_VISIBLE_LOG_CHARS_LIMIT ? (
          <>
            <AnsiHtml
              aria-hidden="true"
              className={cn(
                "text-start z-10 relative",
                "col-start-1 col-end-1 row-start-1 row-end-1",
                "break-all text-wrap whitespace-pre [text-wrap-mode:wrap]"
              )}
              text={content}
            />
            <pre
              className={cn(
                "text-start -z-1 text-transparent relative",
                "col-start-1 col-end-1 row-start-1 row-end-1",
                "break-all text-wrap whitespace-pre [text-wrap-mode:wrap] select-none"
              )}
            >
              {search.length > 0 ? (
                <HighlightedText text={content_text} highlight={search} />
              ) : (
                content_text
              )}
            </pre>
          </>
        ) : (
          <LongLogContent content_text={content_text} search={search} />
        )}
      </div>
    </div>
  );
}

function LongLogContent({
  content_text,
  search
}: { content_text: string; search: string }) {
  const [isFullContentShown, setIsFullContentShown] = React.useState(
    content_text.length <= MAX_VISIBLE_LOG_CHARS_LIMIT
  );

  const visibleContent = isFullContentShown
    ? content_text
    : excerpt(content_text, MAX_VISIBLE_LOG_CHARS_LIMIT);

  return (
    <>
      <pre
        className={cn(
          "text-start z-10  relative",
          "col-start-1 col-end-1 row-start-1 row-end-1",
          "break-all text-wrap whitespace-pre [text-wrap-mode:wrap]"
        )}
      >
        {search.length > 0 ? (
          <HighlightedText text={visibleContent} highlight={search} />
        ) : (
          visibleContent
        )}

        <button
          onClick={() => setIsFullContentShown(!isFullContentShown)}
          className={cn(
            buttonVariants({
              variant: "link"
            }),
            "inline-flex p-0 mx-2 underline h-auto rounded items-center cursor-pointer gap-1",
            "dark:text-primary text-link"
          )}
        >
          <span>{isFullContentShown ? "see less" : "see more"}</span>
          <ChevronRightIcon
            className={cn(
              "flex-none relative top-0.25",
              isFullContentShown && "-rotate-90"
            )}
            size={12}
          />
        </button>
      </pre>
    </>
  );
}

function escapeRegExp(input: string): string {
  return input.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); // $& means the whole matched string
}

const HighlightedText = React.memo(function HighlightedText({
  text,
  highlight
}: { text: string; highlight: string }) {
  // Split on highlight term and include term into parts, ignore case
  const parts = text.split(new RegExp(`(${escapeRegExp(highlight)})`, "gi"));
  return parts.map((part, index) => {
    if (part.toLowerCase() === highlight.toLowerCase()) {
      return (
        <span key={index} className="bg-yellow-400/50">
          {part}
        </span>
      );
    } else {
      return <span key={index}>{part}</span>;
    }
  });
});
