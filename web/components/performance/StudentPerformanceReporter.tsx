"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

import {
  type PerformanceMetricInput,
  recordPerformanceMetric,
} from "@/lib/performance-metrics";

declare global {
  interface Window {
    __deeptutorRouteStartedAt?: number;
  }
}

export default function StudentPerformanceReporter() {
  const pathname = usePathname();
  const recordedColdStart = useRef(false);

  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      const target = event.target instanceof Element ? event.target.closest("a[href]") : null;
      const href = target?.getAttribute("href") ?? "";
      if (href.startsWith("/") && !href.startsWith("//")) {
        window.__deeptutorRouteStartedAt = performance.now();
      }
    };
    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, []);

  useEffect(() => {
    const routeStart = window.__deeptutorRouteStartedAt;
    if (typeof routeStart === "number") {
      recordPerformanceMetric({
        name: "route_visible",
        route: pathname,
        duration_ms: performance.now() - routeStart,
        stage: "committed",
      });
      delete window.__deeptutorRouteStartedAt;
      return;
    }
    if (recordedColdStart.current) return;
    const navigation = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
    if (navigation && navigation.domInteractive > 0) {
      recordPerformanceMetric({
        name: "cold_start_interactive",
        route: pathname,
        duration_ms: navigation.domInteractive - navigation.startTime,
        stage: "interactive",
      });
      recordedColdStart.current = true;
    }
  }, [pathname]);

  useEffect(() => {
    const onMetric = (event: Event) => {
      const detail = (event as CustomEvent<PerformanceMetricInput>).detail;
      if (detail) recordPerformanceMetric(detail);
    };
    window.addEventListener("deeptutor:performance", onMetric);
    return () => window.removeEventListener("deeptutor:performance", onMetric);
  }, []);

  return null;
}
