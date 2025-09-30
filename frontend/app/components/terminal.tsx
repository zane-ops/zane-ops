import * as React from "react";
import { type ITheme, Terminal as XTermTerminal } from "xterm";
import { FitAddon } from "xterm-addon-fit";
import "xterm/css/xterm.css";
import { useTheme } from "~/components/theme-provider";
import { cn } from "~/lib/utils";

type TerminalProps = {
  shellCommand?: string;
  shellUser?: string | null;
  baseWebSocketURL: string;
  className?: string;
};

const shellDarkTheme: ITheme = {
  foreground: "#f8f8f2",
  background: "#1e1e1e",
  cursor: "#f8f8f0",
  cursorAccent: "#1e1e1e",
  selectionBackground: "#44475a",
  black: "#21222c",
  red: "#ff5555",
  green: "#50fa7b",
  yellow: "#f1fa8c",
  blue: "#bd93f9",
  magenta: "#ff79c6",
  cyan: "#8be9fd",
  white: "#f8f8f2",
  brightBlack: "#6272a4",
  brightRed: "#ff6e6e",
  brightGreen: "#69ff94",
  brightYellow: "#ffffa5",
  brightBlue: "#d6acff",
  brightMagenta: "#ff92df",
  brightCyan: "#a4ffff",
  brightWhite: "#ffffff"
};

const shellLightTheme: ITheme = {
  foreground: "#2e3436",
  background: "#ffffff",
  cursor: "#2e3436",
  cursorAccent: "#ffffff",
  selectionBackground: "#c1deff",
  black: "#2e3436",
  red: "#cc0000",
  green: "#4e9a06",
  yellow: "#c4a000",
  blue: "#3465a4",
  magenta: "#75507b",
  cyan: "#06989a",
  white: "#d3d7cf",
  brightBlack: "#555753",
  brightRed: "#ef2929",
  brightGreen: "#8ae234",
  brightYellow: "#fce94f",
  brightBlue: "#729fcf",
  brightMagenta: "#ad7fa8",
  brightCyan: "#34e2e2",
  brightWhite: "#eeeeec"
};

export function Terminal({
  shellCommand = "/bin/sh",
  shellUser,
  baseWebSocketURL,
  className
}: TerminalProps) {
  const terminalRef = React.useRef<HTMLDivElement>(null);
  const term = React.useRef<XTermTerminal>(null);
  const fitAddon = React.useRef<FitAddon>(new FitAddon());
  const socketRef = React.useRef<WebSocket | null>(null);

  const theme = useTheme().theme;

  // Send terminal size to backend over WebSocket
  const sendResize = () => {
    if (!term.current || !socketRef.current) return;
    const cols = term.current.cols;
    const rows = term.current.rows;
    const resizeMessage = JSON.stringify({ type: "resize", cols, rows });
    if (socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(resizeMessage);
    }
  };

  React.useLayoutEffect(() => {
    // Observe container size changes
    // run in `useLayoutEffect()` because it needs to run after dom mutations
    if (!terminalRef.current) return;
    const resizeObserver = new ResizeObserver(() => {
      fitAddon.current.fit();
      sendResize();
    });
    resizeObserver.observe(terminalRef.current);

    return () => {
      resizeObserver.disconnect();
    };
  }, []);

  React.useEffect(() => {
    if (!term.current) return;
    const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");

    let termTheme: ITheme;
    if (theme === "SYSTEM") {
      termTheme = darkQuery.matches ? shellDarkTheme : shellLightTheme;
    } else {
      termTheme = theme === "DARK" ? shellDarkTheme : shellLightTheme;
    }

    term.current.options.theme = termTheme;
  }, [theme]);

  React.useEffect(() => {
    if (!terminalRef.current) return;

    const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");

    let termTheme: ITheme;
    if (theme === "SYSTEM") {
      termTheme = darkQuery.matches ? shellDarkTheme : shellLightTheme;
    } else {
      termTheme = theme === "DARK" ? shellDarkTheme : shellLightTheme;
    }

    // 1. Initialize terminal + fit addon
    term.current = new XTermTerminal({
      cursorBlink: true,
      cols: 80,
      rows: 24,
      fontFamily:
        '"Geist-Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
      fontSize: 14,
      theme: termTheme
    });
    fitAddon.current = new FitAddon();
    term.current.loadAddon(fitAddon.current);

    // 2. Attach terminal to DOM
    term.current.open(terminalRef.current);
    fitAddon.current.fit();

    // 3. Build WebSocket URL with query params
    const params = new URLSearchParams();
    params.set("cmd", encodeURIComponent(shellCommand));
    if (shellUser) {
      params.set("user", encodeURIComponent(shellUser));
    }
    const url = `${baseWebSocketURL}/?${params.toString()}`;

    // 4. Connect
    socketRef.current = new WebSocket(url);

    socketRef.current.onmessage = (event) => {
      if (term.current) {
        term.current.write(event.data);
      }
    };

    socketRef.current.onopen = () => {
      sendResize();
    };

    socketRef.current.onerror = () => {
      if (term.current) {
        term.current.writeln(`\x1b[31mWebSocket error\x1b[0m`);
      }
    };

    socketRef.current.onclose = () => {
      if (term.current) {
        term.current.writeln(`\x1b[33mDisconnected\x1b[0m`);
      }
    };

    // 5. When user types, send to container
    term.current.onData((data) => {
      if (socketRef.current?.readyState === WebSocket.OPEN && term.current) {
        socketRef.current.send(data);
      }
    });

    // Cleanup on unmount
    return () => {
      socketRef.current?.close();
      term.current?.dispose();
    };
  }, [shellCommand, baseWebSocketURL, shellUser]);

  return (
    <div
      ref={terminalRef}
      className={cn("w-full h-full", className)}
      id="terminal"
    />
  );
}
