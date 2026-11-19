// Fictional pickup calls used only by the sample review. The two release cohorts
// match the worked example on the landing page. Every row represents an eligible order.
export const original = "Read the order back before closing.";
export const revision = "Before giving a pickup time, repeat every item and ask the caller to confirm the order.";
const orders = [
  "a large pepperoni and garlic knots",
  "two margheritas",
  "a veggie pizza and a salad",
  "two calzones and garlic bread",
  "a small cheese pizza",
];
const closings = ["Great, it'll be ready in 20 minutes. Bye!", "Perfect, see you soon.", "Thanks! Pickup will be in 20 minutes."];

function sample(release: number, count: number, misses: number) {
  return Array.from({ length: count }, (_, i) => {
    const skipped = Math.ceil(((i + 1) * misses) / count) > Math.ceil((i * misses) / count);
    const order = orders[i % orders.length];
    const turns =
      i === 0 && release === 14
        ? ["Hi, can I get a large pepperoni for pickup?", "Sure thing. Anything else with that?", "Garlic knots. That's it.", closings[0]]
        : [
            `Could I order ${order} for pickup?`,
            "Sure. Anything else?",
            "That's everything.",
            ...(skipped
              ? [closings[i % closings.length]]
              : [`That's ${order}. Is that right?`, "Yes, that's right.", "Great. Pickup in 20 minutes."]),
          ];
    return { id: release * 1000 + i + 1, release, skipped, turns };
  });
}
export const calls = [...sample(14, 206, 37), ...sample(15, 100, 4)];
export const releases = [14, 15].map((version) => {
  const cohort = calls.filter((c) => c.release === version);
  const misses = cohort.filter((c) => c.skipped).length;
  return { version, count: cohort.length, misses, percent: Math.round((100 * misses) / cohort.length) };
});
