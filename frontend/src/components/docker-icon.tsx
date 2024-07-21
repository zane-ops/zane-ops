import * as React from "react";
import { cn } from "~/lib/utils";

export function DockerIcon({ ...props }: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      data-name="Layer 1"
      viewBox="0 0 756.26 596.9"
      {...props}
    >
      <path
        d="M743.96 245.25c-18.54-12.48-67.26-17.81-102.68-8.27-1.91-35.28-20.1-65.01-53.38-90.95l-12.32-8.27-8.21 12.4c-16.14 24.5-22.94 57.14-20.53 86.81 1.9 18.28 8.26 38.83 20.53 53.74-46.1 26.74-88.59 20.67-276.77 20.67H.06c-.85 42.49 5.98 124.23 57.96 190.77 5.74 7.35 12.04 14.46 18.87 21.31 42.26 42.32 106.11 73.35 201.59 73.44 145.66.13 270.46-78.6 346.37-268.97 24.98.41 90.92 4.48 123.19-57.88.79-1.05 8.21-16.54 8.21-16.54l-12.3-8.27Zm-554.29-38.86h-81.7v81.7h81.7v-81.7Zm105.55 0h-81.7v81.7h81.7v-81.7Zm105.55 0h-81.7v81.7h81.7v-81.7Zm105.55 0h-81.7v81.7h81.7v-81.7Zm-422.2 0H2.42v81.7h81.7v-81.7ZM189.67 103.2h-81.7v81.7h81.7v-81.7Zm105.55 0h-81.7v81.7h81.7v-81.7Zm105.55 0h-81.7v81.7h81.7v-81.7Zm0-103.2h-81.7v81.7h81.7V0Z"
        style={{
          fill: "currentColor",
          strokeWidth: 0
        }}
      />
    </svg>
    // <svg
    //   xmlns="http://www.w3.org/2000/svg"
    //   viewBox="0 0 24 24"
    //   {...props}
    //   className={cn(className)}
    //   fill="currentColor"
    // >
    //   <title />
    //   <g data-name="&lt;Group&gt;">
    //     <circle
    //       cx={5.04}
    //       cy={16}
    //       r={0.5}
    //       data-name="&lt;Path&gt;"
    //       style={{
    //         fill: "none",
    //         stroke: "currentColor",
    //         strokeLinecap: "round",
    //         strokeLinejoin: "round"
    //       }}
    //     />
    //     <path
    //       d="M1.5 9.5h3v3h-3zM4.5 9.5h3v3h-3zM7.5 9.5h3v3h-3zM10.5 9.5h3v3h-3zM4.5 6.5h3v3h-3zM7.5 6.5h3v3h-3zM10.5 6.5h3v3h-3zM10.5 3.5h3v3h-3zM13.5 9.5h3v3h-3z"
    //       data-name="&lt;Rectangle&gt;"
    //       style={{
    //         fill: "none",
    //         stroke: "currentColor",
    //         strokeLinecap: "round",
    //         strokeLinejoin: "round"
    //       }}
    //     />
    //     <path
    //       d="M23.5 11.5s-1.75-1.12-3-.5A3.45 3.45 0 0 0 19 8.5a3.64 3.64 0 0 0-.58 2.88 1 1 0 0 1-1 1.12H.5c0 6.25 3.83 8 7.5 8a13.76 13.76 0 0 0 12.06-7 4.68 4.68 0 0 0 3.44-2Z"
    //       data-name="&lt;Path&gt;"
    //       style={{
    //         fill: "none",
    //         stroke: "currentColor",
    //         strokeLinecap: "round",
    //         strokeLinejoin: "round"
    //       }}
    //     />
    //   </g>
    // </svg>
    // <svg
    //   xmlns="http://www.w3.org/2000/svg"
    //   viewBox="0 0 640 512"
    //   {...props}
    //   className={cn(className)}
    //   fill="currentColor"
    // >
    //   <path d="M349.9 236.3h-66.1v-59.4h66.1v59.4zm0-204.3h-66.1v60.7h66.1V32zm78.2 144.8H362v59.4h66.1v-59.4zm-156.3-72.1h-66.1v60.1h66.1v-60.1zm78.1 0h-66.1v60.1h66.1v-60.1zm276.8 100c-14.4-9.7-47.6-13.2-73.1-8.4-3.3-24-16.7-44.9-41.1-63.7l-14-9.3-9.3 14c-18.4 27.8-23.4 73.6-3.7 103.8-8.7 4.7-25.8 11.1-48.4 10.7H2.4c-8.7 50.8 5.8 116.8 44 162.1 37.1 43.9 92.7 66.2 165.4 66.2 157.4 0 273.9-72.5 328.4-204.2 21.4.4 67.6.1 91.3-45.2 1.5-2.5 6.6-13.2 8.5-17.1l-13.3-8.9zm-511.1-27.9h-66v59.4h66.1v-59.4zm78.1 0h-66.1v59.4h66.1v-59.4zm78.1 0h-66.1v59.4h66.1v-59.4zm-78.1-72.1h-66.1v60.1h66.1v-60.1z" />
    // </svg>
  );
}
