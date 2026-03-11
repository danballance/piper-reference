import type { KnipConfig } from "knip";

const config: KnipConfig = {
  ignore: ["src/routeTree.gen.ts", "src/api/generated/**"],
  ignoreUnresolved: ["@/api/generated/.*", "./routeTree.gen"],
  entry: ["src/routes/**/*.tsx"],
};

export default config;
