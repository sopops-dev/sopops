import DefaultTheme from "vitepress/theme";
import { h } from "vue";
import AgentLinks from "./AgentLinks.vue";
import "./raster.css";

export default {
  extends: DefaultTheme,
  Layout: () => h(DefaultTheme.Layout, null, { "doc-before": () => h(AgentLinks) }),
};
