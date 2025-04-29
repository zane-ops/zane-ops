import * as React from "react";
import { Terminal as XTermTerminal } from "xterm";
import { FitAddon } from "xterm-addon-fit";
import "xterm/css/xterm.css";
import { cn } from "~/lib/utils";

type TerminalProps = {
  shellCommand?: string;
  shellUser?: string | null;
  baseWebSocketURL: string;
  className?: string;
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
    if (!terminalRef.current) return;

    // 1. Initialize terminal + fit addon
    term.current = new XTermTerminal({
      cursorBlink: true,
      cols: 80,
      rows: 24,
      fontFamily:
        '"Geist-Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
      fontSize: 14
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
