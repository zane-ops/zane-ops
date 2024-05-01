import { cn } from "~/lib/utils";
import logoSymbolBlack from "/logo/ZaneOps-SYMBOL-BLACK.svg";
import logoSymbolWhite from "/logo/ZaneOps-SYMBOL-WHITE.svg";

import type { FC } from "react";

type LogoProps = {
  className?: string;
};

export const Logo: FC<LogoProps> = ({ className }) => (
  <picture
    className={cn(
      "flex justify-center items-center w-[100px] h-[100px]",
      className
    )}
  >
    <source media="(prefers-color-scheme: dark)" srcSet={logoSymbolWhite} />
    <source media="(prefers-color-scheme: light)" srcSet={logoSymbolBlack} />
    <img src={logoSymbolBlack} alt="Zane logo" />
  </picture>
);
