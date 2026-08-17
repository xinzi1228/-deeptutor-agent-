"use client";

import { Suspense, useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { useTranslation } from "react-i18next";
import { login, fetchAuthStatus, checkIsFirstUser } from "@/lib/auth";
import { setViewIdentity } from "@/lib/view-identity";

function LoginPageContent() {
  const { t } = useTranslation();
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") ?? "/";

  const registered = searchParams.get("registered") === "1";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const [identity, setIdentity] = useState<"student" | "staff">("student");
  const [authEnabled, setAuthEnabled] = useState<boolean | null>(null);

  useEffect(() => {
    // If already authenticated, skip login
    fetchAuthStatus().then((status) => {
      setAuthEnabled(status?.enabled ?? true);
      if (status?.authenticated) {
        router.replace(next);
        return;
      }
      // No users registered yet — send straight to the registration page
      checkIsFirstUser().then((first) => {
        if (first) router.replace("/register");
      });
    });
  }, [router, next]);

  function handleIdentityEnter() {
    setViewIdentity(identity);
    router.replace(identity === "student" ? "/home" : "/admin");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    const result = await login(username, password);

    if (result.ok) {
      router.replace(next);
    } else {
      setError(result.error ?? t("Login failed"));
      setLoading(false);
    }
  }

  return (
    <div className="w-full max-w-sm">
      {/* Logo / Title */}
      <div className="text-center mb-8">
        <Image src="/brand-logo.png" alt="标注星图｜智标数据·点亮学习" width={360} height={360} priority className="mx-auto h-auto w-44" />
        <p className="mt-1 text-sm text-[var(--muted-foreground)]">
          {t("Sign in to your account")}
        </p>
      </div>

      {/* Registered success notice */}
      {registered && (
        <div className="mb-4 rounded-lg border border-green-500/30 bg-green-500/10 px-4 py-3 text-sm text-green-600 dark:text-green-400">
          {t("Account created! Sign in to continue.")}
        </div>
      )}

      {/* Card */}
      <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl shadow-sm px-8 py-8">
        {authEnabled === null ? (
          <p className="text-center text-sm text-[var(--muted-foreground)]">
            {t("Loading…")}
          </p>
        ) : authEnabled === false ? (
          <div className="space-y-5">
            <div className="grid grid-cols-2 gap-2">
              {(["student", "staff"] as const).map((id) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setIdentity(id)}
                  className={`rounded-xl border px-3 py-4 text-sm transition-colors ${
                    identity === id
                      ? "border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--primary)]"
                      : "border-[var(--border)] hover:bg-[var(--muted)]"
                  }`}
                >
                  <span className="block font-medium">
                    {id === "student" ? "学生" : "教师或管理员"}
                  </span>
                  <span className="mt-1 block text-xs text-[var(--muted-foreground)]">
                    {id === "student" ? "学习、实训、成长、我的" : "五中心工作台与教师管理"}
                  </span>
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={handleIdentityEnter}
              className="w-full py-2.5 px-4 rounded-lg font-medium text-sm
                         bg-[var(--primary)] text-[var(--primary-foreground)]
                         hover:opacity-90 active:opacity-80 transition-opacity"
            >
              进入
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
          {/* Email or username */}
          <div>
            <label
              htmlFor="username"
              className="block text-sm font-medium text-[var(--foreground)] mb-1.5"
            >
              {t("Email or username")}
            </label>
            <input
              id="username"
              type="text"
              autoComplete="username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-lg border border-[var(--border)]
                         bg-[var(--background)] text-[var(--foreground)]
                         placeholder:text-[var(--muted-foreground)]
                         focus:outline-none focus:ring-2 focus:ring-[var(--primary)] focus:border-transparent
                         transition-shadow text-sm"
              placeholder="you@example.com"
            />
          </div>

          {/* Password */}
          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium text-[var(--foreground)] mb-1.5"
            >
              {t("Password")}
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-lg border border-[var(--border)]
                         bg-[var(--background)] text-[var(--foreground)]
                         placeholder:text-[var(--muted-foreground)]
                         focus:outline-none focus:ring-2 focus:ring-[var(--primary)] focus:border-transparent
                         transition-shadow text-sm"
              placeholder="••••••••"
            />
          </div>

          {/* Error message */}
          {error && (
            <p className="text-sm text-red-500 bg-red-500/10 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 px-4 rounded-lg font-medium text-sm
                       bg-[var(--primary)] text-[var(--primary-foreground)]
                       hover:opacity-90 active:opacity-80
                       disabled:opacity-50 disabled:cursor-not-allowed
                       transition-opacity"
          >
            {loading ? t("Signing in…") : t("Sign in")}
          </button>
          </form>
        )}
      </div>

      <p className="mt-6 text-center text-sm text-[var(--muted-foreground)]">
        {t("Don't have an account?")}{" "}
        <Link
          href="/register"
          className="text-[var(--primary)] hover:underline font-medium"
        >
          {t("Create one")}
        </Link>
      </p>

      <p className="mt-3 text-center text-xs text-[var(--muted-foreground)]">
        标注星图 · Agent-Native Learning
      </p>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="w-full max-w-sm text-center text-sm text-[var(--muted-foreground)]">
          Loading sign in...
        </div>
      }
    >
      <LoginPageContent />
    </Suspense>
  );
}
