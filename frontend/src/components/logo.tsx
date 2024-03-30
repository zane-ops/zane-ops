import logoSymbolBlack from "/logo/ZaneOps-SYMBOL-BLACK.svg";
import logoSymbolWhite from "/logo/ZaneOps-SYMBOL-WHITE.svg";

export function Logo({ className = "hidden" }: { className: string }) {
  return (
    <picture
      className={`md:${className} w-[100px] h-[100px] flex justify-center items-center`}
    >
      <source media="(prefers-color-scheme: dark)" srcSet={logoSymbolWhite} />
      <source media="(prefers-color-scheme: light)" srcSet={logoSymbolBlack} />
      <img src={logoSymbolBlack} alt="Zane logo" />
    </picture>
  );
}
