import { notFoundResponse } from "./not-found.js";

export default {
  async fetch(request, env) {
    return notFoundResponse(request, await env.ASSETS.fetch(request), "https://sopops.dev/docs/llms.txt");
  },
};
