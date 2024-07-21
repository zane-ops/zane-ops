import starlight from "@astrojs/starlight";
import { defineConfig } from "astro/config";

import tailwind from "@astrojs/tailwind";

// https://astro.build/config
export default defineConfig({
  site: "https://zane.fredkiss.dev",
  base: "/docs",
  integrations: [
    starlight({
      title: "ZaneOps documentation",
      logo: {
        light: "./src/assets/ZaneOps-SYMBOL-BLACK.svg",
        dark: "./src/assets/ZaneOps-SYMBOL-WHITE.svg",
        replacesTitle: true
      },
      editLink: {
        baseUrl: "https://github.com/zane-ops/zane-ops/edit/main/docs/"
      },
      customCss: [
        "./src/tailwind.css",
        "./src/assets/theme.css",
        "./src/assets/fonts/font-face.css"
      ],
      social: {
        github: "https://github.com/zane-ops/zane-ops",
        twitter: "https://twitter.com/zaneopsdev"
      },
      sidebar: [
        {
          label: "Start here",
          items: [
            {
              label: "Get started",
              slug: "get-started"
            },
            {
              label: "Screenshots",
              slug: "screenshots"
            }
          ]
        }
        // {
        //   label: "Reference",
        //   autogenerate: {
        //     directory: "reference"
        //   }
        // }
      ]
    }),
    tailwind({
      applyBaseStyles: false
    })
  ]
});
