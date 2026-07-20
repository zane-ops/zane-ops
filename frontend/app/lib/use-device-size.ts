import { useMediaQuery } from "@uidotdev/usehooks";

export type DeviceSize = "phone" | "tablet" | "desktop" | "wide-screen";

export function useDeviceSize(): DeviceSize {
  const isPhone = useMediaQuery("only screen and (max-width : 768px)");
  const isTablet = useMediaQuery(
    "only screen and (min-width : 769px) and (max-width : 992px)"
  );
  const isDesktop = useMediaQuery(
    "only screen and (min-width : 993px) and (max-width : 1200px)"
  );

  if (isPhone) return "phone";
  if (isTablet) return "tablet";
  if (isDesktop) return "desktop";
  return "wide-screen";
}
