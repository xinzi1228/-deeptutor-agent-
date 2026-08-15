import AdminNav from "@/components/admin/AdminNav";
import RoleRouteGate from "@/components/admin/RoleRouteGate";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <RoleRouteGate>
      <div className="flex h-screen overflow-hidden bg-[var(--background)]">
        <AdminNav />
        <main className="min-w-0 flex-1 overflow-y-auto">{children}</main>
      </div>
    </RoleRouteGate>
  );
}
