import { useNProgress } from "@tanem/react-nprogress";
import { useNavigation } from "react-router";
import { useSpinDelay } from "spin-delay";
import { SPIN_DELAY_DEFAULT_OPTIONS } from "~/lib/constants";
import { cn } from "~/lib/utils";

type NavigationProgressProps = {
  className?: string;
};

export function NavigationProgress({ className }: NavigationProgressProps) {
  const navigation = useNavigation();
  const isAnimating = useSpinDelay(
    navigation.state === "loading",
    SPIN_DELAY_DEFAULT_OPTIONS
  );

  const { animationDuration, isFinished, progress } = useNProgress({
    isAnimating
  });

  return (
    <div
      className={cn(
        "pointer-events-none",
        isFinished ? "opacity-0" : "opacity-100",
        className
      )}
      style={{
        transition: `opacity ${animationDuration}ms linear`
      }}
    >
      <div
        className="bg-primary h-1 fixed left-0 top-0 w-full z-1031"
        style={{
          marginLeft: `${(-1 + progress) * 100}%`,
          transition: `margin-left ${animationDuration}ms linear`
        }}
      />
    </div>
  );
}
