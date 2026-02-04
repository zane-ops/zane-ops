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
    <>
      <img
        src={logoSymbolWhite}
        alt="Zane logo"
        className={cn(
          "flex justify-center items-center size-[100px] flex-none",
          "!hidden dark:!block",
          className
        )}
      />
      <img
        src={logoSymbolBlack}
        alt="Zane logo"
        className={cn(
          "flex justify-center items-center size-[100px] flex-none",
          "block dark:hidden",
          className
        )}
      />
    </>
  );
}

export function ZaneOpsLogo(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      data-name="Layer 1"
      viewBox="0 0 820.25 778.36"
      {...props}
    >
      <path
        d="M739.11 389.19c0 37.87-12.19 72.88-32.85 101.33-17.63 24.33-41.47 43.84-69.18 56.25-21.47 9.62-45.26 14.97-70.3 14.97H81.15v-70.46l.76-.76L284.13 288.3H81.15v-71.21h304.44v70.46l-.76.76-202.21 202.22h119.02l276.65.01c.01-.01.04-.01.05-.01 50.83-5.73 90.31-48.92 90.31-101.33 0-56.34-45.6-102.01-101.87-102.01S464.91 332.87 464.91 389.2c0 3.46.17 6.88.51 10.24l-57.08 57.69c-8.94-20.85-13.89-43.81-13.89-67.94 0-95.3 77.16-172.56 172.33-172.56s172.33 77.26 172.33 172.56Z"
        style={{
          fill: "currentColor",
          strokeWidth: 0
        }}
      />
    </svg>
  );
}
