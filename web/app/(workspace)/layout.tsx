import WorkspaceSidebar from "@/components/sidebar/WorkspaceSidebar";
import { CapabilityAccessProvider } from "@/components/access/CapabilityAccessContext";
import CapabilityGate from "@/components/access/CapabilityGate";
import { UnifiedChatProvider } from "@/context/UnifiedChatContext";
import { LearningProfileProvider } from "@/components/learning-profiles/LearningProfileContext";
import { ProfileLockBanner } from "@/components/learning-profiles/ProfileLockBanner";
import StudentPerformanceReporter from "@/components/performance/StudentPerformanceReporter";
import { CurrentLearningTaskProvider } from "@/components/current-task/CurrentLearningTaskContext";
import CurrentTaskBar from "@/components/current-task/CurrentTaskBar";

export default function WorkspaceLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <CapabilityAccessProvider>
      <LearningProfileProvider>
        <CurrentLearningTaskProvider>
          <UnifiedChatProvider>
        <StudentPerformanceReporter />
        <div className="flex h-screen overflow-hidden">
          <WorkspaceSidebar />
          <main className="flex min-w-0 flex-1 flex-col overflow-hidden bg-[var(--background)]">
            <CurrentTaskBar />
            <div className="min-h-0 flex-1 overflow-hidden">
            <CapabilityGate><ProfileLockBanner>{children}</ProfileLockBanner></CapabilityGate>
            </div>
          </main>
        </div>
          </UnifiedChatProvider>
        </CurrentLearningTaskProvider>
      </LearningProfileProvider>
    </CapabilityAccessProvider>
  );
}
