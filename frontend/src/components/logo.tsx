import { cn } from "~/lib/utils";
import logoSymbolBlack from "/logo/ZaneOps-SYMBOL-BLACK.svg";
import logoSymbolWhite from "/logo/ZaneOps-SYMBOL-WHITE.svg";

export function Logo({ className }: { className?: string }) {
  return (
    <picture
      className={cn(
        "flex justify-center items-center w-[60px] h-[60px]",
        className
      )}
    >
      <source media="(prefers-color-scheme: dark)" srcSet={logoSymbolWhite} />
      <source media="(prefers-color-scheme: light)" srcSet={logoSymbolBlack} />
      <img src={logoSymbolBlack} alt="Zane logo" />
    </picture>
  );
}
