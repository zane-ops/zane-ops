type TrackerColor = "red" | "green" | "yellow";
export function getBadgeColor(tracker: number): TrackerColor {
  switch (tracker) {
    case 0:
      return "red";
    case 1:
      return "green";
    case 2:
      return "yellow";
    default:
      return "green";
  }
}
