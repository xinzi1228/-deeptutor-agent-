"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { fetchAuthStatus } from "@/lib/auth";
import { hasChosenIdentity } from "@/lib/view-identity";

/**
 * Root page: 首次访问引导身份选择，已有身份直接进对应端。
 * Handles backward compatibility for /?session=xxx URLs.
 */
export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sessionId = params.get("session");
    const capability = params.get("capability");
    const tools = params.getAll("tool");

    let target = sessionId ? `/home/${sessionId}` : "/home";

    const query: string[] = [];
    if (capability) query.push(`capability=${encodeURIComponent(capability)}`);
    tools.forEach((t) => query.push(`tool=${encodeURIComponent(t)}`));
    if (query.length) target += `?${query.join("&")}`;

    if (sessionId) {
      router.replace(target);
      return;
    }

    // AUTH 关闭时的首次访问引导：未选身份 → /login 选身份。AUTH 开启时登录
    // 由 proxy gate 负责（未登录不会到本页），已登录用户直接进 /home，不受
    // 身份引导拦截。
    fetchAuthStatus().then((status) => {
      if (status?.enabled) {
        router.replace(target);
        return;
      }
      if (!hasChosenIdentity()) {
        router.replace("/login");
        return;
      }
      router.replace(target);
    });
  }, [router]);

  return null;
}
