import WorkspaceSidebar from "@/components/sidebar/WorkspaceSidebar";
import { CapabilityAccessProvider } from "@/components/access/CapabilityAccessContext";
import CapabilityGate from "@/components/access/CapabilityGate";
import { UnifiedChatProvider } from "@/context/UnifiedChatContext";
import { LearningProfileProvider } from "@/components/learning-profiles/LearningProfileContext";
import { ProfileLockBanner } from "@/components/learning-profiles/ProfileLockBanner";
import StudentPerformanceReporter from "@/components/performance/StudentPerformanceReporter";

export default function WorkspaceLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <CapabilityAccessProvider>
      <LearningProfileProvider>
        <UnifiedChatProvider>
        <StudentPerformanceReporter />
        <div className="flex h-screen overflow-hidden">
          <WorkspaceSidebar />
          <main className="flex-1 overflow-hidden bg-[var(--background)]">
            <CapabilityGate><ProfileLockBanner>{children}</ProfileLockBanner></CapabilityGate>
          </main>
        </div>
        </UnifiedChatProvider>
      </LearningProfileProvider>
    </CapabilityAccessProvider>
  );
}
