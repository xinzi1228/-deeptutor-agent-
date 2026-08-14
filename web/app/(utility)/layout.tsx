import UtilitySidebar from "@/components/sidebar/UtilitySidebar";
import { CapabilityAccessProvider } from "@/components/access/CapabilityAccessContext";
import CapabilityGate from "@/components/access/CapabilityGate";
import StudentRouteGate from "@/components/access/StudentRouteGate";

export default function UtilityLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <CapabilityAccessProvider>
      <div className="flex h-screen overflow-hidden">
        <UtilitySidebar />
        <main className="flex-1 overflow-hidden bg-[var(--background)]">
          <StudentRouteGate><CapabilityGate>{children}</CapabilityGate></StudentRouteGate>
        </main>
      </div>
    </CapabilityAccessProvider>
  );
}
