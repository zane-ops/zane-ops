import { useTheme } from "~/components/theme-provider";
import { cn } from "~/lib/utils";
import logoSymbolBlack from "/logo/ZaneOps-SYMBOL-BLACK.svg";
import logoSymbolWhite from "/logo/ZaneOps-SYMBOL-WHITE.svg";

export function ThemedLogo({ className }: { className?: string }) {
  const theme = useTheme().theme;
  return (
    <picture
      className={cn(
        "flex justify-center items-center size-[100px] flex-none",
        className
      )}
    >
      {theme === "SYSTEM" && (
        <>
          <source
            media="(prefers-color-scheme: dark)"
            srcSet={logoSymbolWhite}
          />
          <source
            media="(prefers-color-scheme: light)"
            srcSet={logoSymbolBlack}
          />
        </>
      )}
      <img
        src={theme === "DARK" ? logoSymbolWhite : logoSymbolBlack}
        alt="Zane logo"
      />
    </picture>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <picture
      className={cn(
        "flex justify-center items-center size-[100px] flex-none",
        className
      )}
    >
      <source media="(prefers-color-scheme: dark)" srcSet={logoSymbolWhite} />
      <source media="(prefers-color-scheme: light)" srcSet={logoSymbolBlack} />
      <img src={logoSymbolBlack} alt="Zane logo" />
    </picture>
  );
}
