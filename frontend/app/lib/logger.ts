type LogArgs = Parameters<typeof console.log>;

export interface DevLogger {
  /** shorthand for `logger.log(...)` */
  (...args: LogArgs): void;
  log(...args: LogArgs): void;
  info(...args: LogArgs): void;
  warn(...args: LogArgs): void;
  error(...args: LogArgs): void;
  /** narrow the logger down: `[file]` -> `[file/fn]` */
  scope(...scopes: string[]): DevLogger;
  /** the computed `[file/fn]` prefix, ex: for `console.time(logger.prefix)` */
  readonly prefix: string;
}

/**
 * Turn `/app/routes/layouts/workspace-layout.tsx?t=123` into `workspace-layout`,
 * and leave plain names (`getQueryClient`) untouched.
 */
function toModuleName(source: string | ImportMeta) {
  const url = typeof source === "string" ? source : source.url;
  if (!url.includes("/") && !url.includes(".")) return url;

  const fileName = url.split("?")[0].split("/").pop() ?? url;
  return fileName.replace(/\.[^.]+$/, "");
}

/** the module this file is served from, so we can skip our own stack frames */
const SELF = import.meta.url.split("?")[0];

/**
 * Best-effort name of the function that called the logger, read from the
 * stack trace. Returns `undefined` for anonymous callers.
 */
function callerName() {
  const limit = Error.stackTraceLimit;
  // we only need our own frames + the caller
  Error.stackTraceLimit = 5;
  const stack = new Error().stack;
  Error.stackTraceLimit = limit;
  if (!stack) return undefined;

  // the first frame that isn't this file is the caller
  const frame = stack
    .split("\n")
    .find((line) => /(^\s*at\s)|@/.test(line) && !line.includes(SELF));
  if (!frame) return undefined;

  // V8: `    at Object.getQueryClient (http://host/app/lib/x.ts:26:14)`
  // SpiderMonkey/JSC: `getQueryClient@http://host/app/lib/x.ts:26:14`
  const name =
    frame.match(/^\s*at\s+(?:async\s+)?([^\s(]+)\s*\(/)?.[1] ??
    frame.match(/^\s*([^@\s]+)@/)?.[1];
  if (!name || name === "<anonymous>") return undefined;

  // strip the `Object.` / `Module.` / `Proxy.` receiver prefixes V8 adds
  const shortName = name.split(".").pop();
  return shortName && shortName !== "<anonymous>" ? shortName : undefined;
}

function makeLogger(scopes: string[], derive: boolean): DevLogger {
  const prefix = `[${scopes.join("/")}]`;

  const write =
    (method: "log" | "info" | "warn" | "error") =>
    (...args: LogArgs) => {
      if (!import.meta.env.DEV) return;
      const caller = derive ? callerName() : undefined;
      console[method](
        caller ? `[${[...scopes, caller].join("/")}]` : prefix,
        ...args
      );
    };

  const logger = write("log") as DevLogger;
  logger.log = write("log");
  logger.info = write("info");
  logger.warn = write("warn");
  logger.error = write("error");
  logger.scope = (...children: string[]) =>
    makeLogger([...scopes, ...children.filter(Boolean)], false);

  Object.defineProperty(logger, "prefix", { value: prefix });
  return logger;
}

/**
 * A `console.log` wrapper that only prints in DEV and prefixes
 * every message with `[file-name/function]`.
 *
 * The calling function name is read from the stack trace, so most of the time
 * there is nothing to pass:
 *
 * ```ts
 * // app/routes/layouts/workspace-layout.tsx
 * const logger = createDevLogger(import.meta.url);
 *
 * export async function clientLoader() {
 *   logger("redirect to `/`"); // [workspace-layout/clientLoader] redirect to `/`
 *   logger.warn("no workspace", { user }); // console.warn, same prefix
 * }
 * ```
 *
 * Anonymous callers (inline callbacks, IIFEs...) have no name to derive, and
 * the derived name is the *innermost* function, which isn't always the one you
 * mean. Use `logger.scope("name")` to pin the scope down in those cases.
 */
export function createDevLogger(
  source: string | ImportMeta,
  ...scopes: string[]
): DevLogger {
  const explicit = scopes.filter(Boolean);
  return makeLogger([toModuleName(source), ...explicit], explicit.length === 0);
}
