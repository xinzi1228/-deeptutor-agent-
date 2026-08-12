"use client";

import { useEffect, useState } from "react";
import { GitBranch, ChevronRight, ChevronDown, BookOpen } from "lucide-react";

interface SkillNode {
  id: string;
  name: string;
  level: number;
  description?: string;
  skills?: SkillNode[];
  children?: SkillNode[];
}

export default function CompetencyPage() {
  const [tree, setTree] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/v1/profile/competency-tree")
      .then((r) => r.json())
      .then((data) => {
        setTree(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-[var(--muted-foreground)]">
        加载中...
      </div>
    );
  }

  if (!tree?.tree) {
    return (
      <div className="flex h-full items-center justify-center text-[var(--muted-foreground)]">
        暂无能力树数据
      </div>
    );
  }

  const groups = tree.tree.children || [];

  return (
    <div className="flex h-full flex-col bg-[var(--background)]">
      <header className="flex items-center gap-3 border-b border-[var(--border)] px-6 py-3">
        <GitBranch className="h-5 w-5 text-[var(--muted-foreground)]" />
        <div>
          <h1 className="text-[15px] font-semibold text-[var(--foreground)]">
            能力树
          </h1>
          <p className="text-[11px] text-[var(--muted-foreground)]">
            {tree.role || "AI数据标注工程师"} · {groups.length} 个能力组
          </p>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="mb-6">
          <p className="text-sm text-[var(--muted-foreground)]">
            {tree.description || ""}
          </p>
          {tree.standards && (
            <div className="mt-2 flex flex-wrap gap-2">
              {(tree.standards as string[]).map((s: string, i: number) => (
                <span
                  key={i}
                  className="rounded-full bg-[var(--card)] px-3 py-1 text-[10px] text-[var(--muted-foreground)] border border-[var(--border)]"
                >
                  {s}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="space-y-4">
          {groups.map((group: any, gi: number) => (
            <GroupCard key={group.id || gi} group={group} defaultOpen={gi < 5} />
          ))}
        </div>
      </div>
    </div>
  );
}

function GroupCard({
  group,
  defaultOpen,
}: {
  group: any;
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  const subgroups = group.children || [];
  const totalSkills = subgroups.reduce(
    (sum: number, sg: any) => sum + (sg.skills?.length || 0),
    0
  );

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--card)]">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 px-4 py-3 text-left hover:bg-[var(--muted)]/30 rounded-t-lg"
      >
        {open ? (
          <ChevronDown className="h-4 w-4 text-[var(--muted-foreground)]" />
        ) : (
          <ChevronRight className="h-4 w-4 text-[var(--muted-foreground)]" />
        )}
        <span className="text-sm font-semibold text-[var(--foreground)]">
          {group.name}
        </span>
        <span className="ml-auto text-[10px] text-[var(--muted-foreground)]">
          {subgroups.length} 子类 · {totalSkills} 技能
        </span>
      </button>

      {open && (
        <div className="border-t border-[var(--border)] px-4 py-3">
          {group.description && (
            <p className="mb-3 text-[11px] text-[var(--muted-foreground)]">
              {group.description}
            </p>
          )}
          <div className="space-y-3">
            {subgroups.map((sg: any, sgi: number) => (
              <SubGroup key={sg.id || sgi} subgroup={sg} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function SubGroup({ subgroup }: { subgroup: any }) {
  const [open, setOpen] = useState(true);
  const skills = subgroup.skills || [];

  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-xs font-medium text-[var(--foreground)] hover:text-[var(--primary)]"
      >
        {open ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
        {subgroup.name}
        <span className="text-[10px] text-[var(--muted-foreground)]">
          ({skills.length})
        </span>
      </button>

      {open && (
        <div className="mt-2 space-y-1 pl-5">
          {skills.map((skill: any, si: number) => (
            <div
              key={skill.id || si}
              className="flex items-start gap-2 rounded-md px-3 py-2 hover:bg-[var(--muted)]/20"
            >
              <BookOpen className="mt-0.5 h-3 w-3 flex-shrink-0 text-[var(--muted-foreground)]" />
              <div>
                <div className="text-xs font-medium text-[var(--foreground)]">
                  {skill.name}
                </div>
                {skill.description && (
                  <div className="text-[10px] text-[var(--muted-foreground)] mt-0.5">
                    {skill.description}
                  </div>
                )}
                {skill.source && (
                  <span className="inline-block mt-1 rounded bg-[var(--primary)]/10 px-1.5 py-0.5 text-[9px] text-[var(--primary)]">
                    {skill.source}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
