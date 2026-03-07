import type { KnipConfig } from "knip";

const config: KnipConfig = {
  ignore: ["src/routeTree.gen.ts"],
  entry: ["src/main.tsx", "src/routes/**/*.tsx"],
};

export default config;
