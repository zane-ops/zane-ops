declare const __BUILD_ID__: string;
import * as React from "react";

declare module "react" {
  interface CSSProperties {
    // css variables definition
    [key: `--${string}`]: string | number | undefined | null;
  }
}
