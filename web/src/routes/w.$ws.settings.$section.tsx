import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Note } from "@/components/bits";
import { ExtensionSettings } from "@/components/extension-settings";
import { SectionHead, useExtensionSections } from "@/components/settings";
import { q } from "@/lib/api";

// A page an extension adds to Settings (/settings/<its id>). The built-in sections have their own routes, which win.
export const Route = createFileRoute("/w/$ws/settings/$section")({ component: ExtensionPage });

function ExtensionPage() {
  const { ws, section } = Route.useParams();
  const sections = useExtensionSections(ws);
  const loading = useQuery(q.settingsSections(ws)).isPending;
  const found = sections.find((s) => s.id === section);
  if (found) return <ExtensionSettings section={found} />;
  if (loading) return null;
  return (
    <>
      <SectionHead title="Settings" />
      <Note>There's no {section} section here.</Note>
    </>
  );
}
