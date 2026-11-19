import { createFileRoute, notFound, redirect } from "@tanstack/react-router";
import { DEMO, DEMO_WS } from "@/lib/demo";
import { startTour } from "@/components/tour";
import { reviewRule, reviewSessionId } from "@/lib/demo-review";

export const Route = createFileRoute("/call-review")({
  beforeLoad: ({ preload }) => {
    if (!DEMO) throw notFound();
    if (!preload) startTour(DEMO_WS);
    throw redirect({
      to: "/w/$ws/sessions/$id",
      params: { ws: DEMO_WS, id: reviewSessionId },
      search: { procedure: "delivery-orders", rule: reviewRule },
      replace: true,
    });
  },
});
