import { useEffect, useRef, useState } from "react"
import { ArrowLeft, ArrowRight, Eye, EyeOff, Lock, ShieldCheck, ShieldOff, UserCheck } from "lucide-react"
import { cn } from "@/lib/utils"
import { ApiError, loginWithPin, type SessionInfo } from "@/lib/api"

type Role = "viewer" | "editor"

const ROLES: {
  id: Role
  title: string
  blurb: string
  points: string[]
  tone: "info" | "warn"
  icon: typeof UserCheck
}[] = [
  {
    id: "viewer",
    title: "General",
    blurb: "Read-only access to signals, scanners and the system monitor.",
    points: ["See every signal and chart", "Browse scanners", "Cannot change anything"],
    tone: "info",
    icon: UserCheck,
  },
  {
    id: "editor",
    title: "Editor",
    blurb: "Full control: install scanners, send test alerts, change settings.",
    points: ["Everything General can do", "Install / remove scanners", "Send alerts, edit setup"],
    tone: "warn",
    icon: ShieldCheck,
  },
]

export function LoginPage({
  session,
  onAuthed,
}: {
  session: SessionInfo
  onAuthed: (role: Role) => void
}) {
  const [role, setRole] = useState<Role | null>(null)
  const [pin, setPin] = useState("")
  const [showPin, setShowPin] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lockLeft, setLockLeft] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (role) inputRef.current?.focus()
  }, [role])

  useEffect(() => {
    if (lockLeft <= 0) return
    const timer = window.setInterval(() => setLockLeft((current) => Math.max(0, current - 1)), 1000)
    return () => window.clearInterval(timer)
  }, [lockLeft])

  const chosen = ROLES.find((item) => item.id === role) ?? null
  const pinMissing = role ? !session.pins[role] : false

  const submit = async () => {
    if (!role || busy || lockLeft > 0) return
    if (!pin.trim()) {
      setError("Enter the PIN for this role.")
      return
    }
    setBusy(true)
    setError(null)
    try {
      const next = await loginWithPin(role, pin)
      onAuthed((next.role as Role) ?? role)
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 429) {
          const payload = err.payload as { retryAfter?: number } | undefined
          const wait = payload?.retryAfter && payload.retryAfter > 0 ? payload.retryAfter : 60
          setLockLeft(wait)
          setError(`Too many attempts. Try again in ${wait}s.`)
        } else if (err.status === 409) {
          setError("No PIN is set for this role yet. Ask the owner to run `asta pins set`.")
        } else if (err.status === 401) {
          setError("Wrong PIN for this role.")
        } else if (err.status === 403) {
          setError("View-only session: pick Editor to make changes.")
        } else {
          setError(err.message)
        }
      } else {
        setError(err instanceof Error ? err.message : "Sign-in failed.")
      }
      setPin("")
      inputRef.current?.focus()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="relative grid min-h-screen place-items-center px-4 py-10">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(120%_80%_at_50%_-10%,var(--color-info-soft),transparent_60%)]"
      />
      <div className="relative w-full max-w-[560px]">
        <div className="mb-5 flex items-center gap-2">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-info text-[13px] font-bold text-white">
            A
          </span>
          <div>
            <div className="text-[14px] font-semibold text-ink">ASTA</div>
            <div className="text-[11px] text-faint">Signal engine · dashboard access</div>
          </div>
        </div>

        <div className="rounded-2xl border border-line bg-surface/90 p-5 shadow-xl backdrop-blur">
          {role === null ? (
            <>
              <div className="mb-4">
                <div className="text-[13.5px] font-semibold text-ink">Choose your role</div>
                <p className="mt-1 text-[11.5px] leading-relaxed text-faint">
                  Each role has its own PIN. Pick the one you were given — the PIN decides what you can do,
                  the choice only tells us which PIN to check.
                </p>
              </div>
              <div className="space-y-2">
                {ROLES.map((item) => {
                  const Icon = item.icon
                  const available = session.pins[item.id]
                  return (
                    <button
                      key={item.id}
                      type="button"
                      disabled={!available}
                      onClick={() => {
                        setRole(item.id)
                        setError(null)
                        setPin("")
                      }}
                      className={cn(
                        "group flex w-full items-start gap-3 rounded-xl border px-3.5 py-3 text-left transition-colors",
                        available
                          ? "cursor-pointer border-line bg-surface-2 hover:border-info/40 hover:bg-info-soft/40"
                          : "cursor-not-allowed border-line-soft bg-surface-2/40 opacity-60",
                      )}
                    >
                      <span
                        className={cn(
                          "mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg",
                          item.tone === "warn" ? "bg-warn-soft text-warn" : "bg-info-soft text-info",
                        )}
                      >
                        <Icon className="h-3.5 w-3.5" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center gap-2">
                          <span className="text-[12.5px] font-semibold text-ink">{item.title}</span>
                          {!available ? (
                            <span className="rounded-full bg-surface-3 px-1.5 py-0.5 text-[9.5px] font-medium text-faint">
                              no PIN set
                            </span>
                          ) : null}
                        </span>
                        <span className="mt-0.5 block text-[11px] leading-relaxed text-faint">
                          {item.blurb}
                        </span>
                        <span className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-faint">
                          {item.points.map((point) => (
                            <span key={point} className="inline-flex items-center gap-1">
                              <span className="h-1 w-1 rounded-full bg-current opacity-50" />
                              {point}
                            </span>
                          ))}
                        </span>
                      </span>
                      <ArrowRight className="mt-1 h-3.5 w-3.5 shrink-0 text-faint transition-transform group-hover:translate-x-0.5" />
                    </button>
                  )
                })}
              </div>
              {session.tokenRequired ? (
                <p className="mt-3 text-[10.5px] leading-relaxed text-faint">
                  A share link with <code className="font-mono">?token=</code> still works and skips this screen.
                </p>
              ) : null}
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={() => {
                  setRole(null)
                  setPin("")
                  setError(null)
                }}
                className="mb-3 inline-flex cursor-pointer items-center gap-1 text-[11px] font-medium text-faint hover:text-ink"
              >
                <ArrowLeft className="h-3 w-3" /> Change role
              </button>

              <div className="mb-3 flex items-center gap-2">
                <span
                  className={cn(
                    "grid h-7 w-7 place-items-center rounded-lg",
                    chosen?.tone === "warn" ? "bg-warn-soft text-warn" : "bg-info-soft text-info",
                  )}
                >
                  {chosen ? <chosen.icon className="h-3.5 w-3.5" /> : <Lock className="h-3.5 w-3.5" />}
                </span>
                <div>
                  <div className="text-[13px] font-semibold text-ink">{chosen?.title} PIN</div>
                  <div className="text-[10.5px] text-faint">
                    {chosen?.id === "editor"
                      ? "Editor access can install scanners — keep this PIN to yourself."
                      : "Read-only access. Safe to share with people you trust."}
                  </div>
                </div>
              </div>

              <form
                onSubmit={(event) => {
                  event.preventDefault()
                  void submit()
                }}
              >
                <div className="flex items-center gap-2">
                  <div className="relative flex-1">
                    <input
                      ref={inputRef}
                      type={showPin ? "text" : "password"}
                      value={pin}
                      onChange={(event) => {
                        setPin(event.target.value)
                        setError(null)
                      }}
                      inputMode="numeric"
                      autoComplete="off"
                      autoCapitalize="off"
                      spellCheck={false}
                      maxLength={64}
                      placeholder="••••••"
                      disabled={busy || lockLeft > 0 || pinMissing}
                      className={cn(
                        "h-10 w-full rounded-xl border bg-surface-2 px-3 pr-10 font-mono text-[15px] tracking-[0.3em] text-ink outline-none transition-colors",
                        error ? "border-down/50 focus:border-down" : "border-line focus:border-info",
                        "disabled:opacity-60",
                      )}
                      aria-label={`${chosen?.title} PIN`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPin((current) => !current)}
                      className="absolute right-1.5 top-1/2 grid h-7 w-7 -translate-y-1/2 cursor-pointer place-items-center rounded-lg text-faint hover:bg-surface-3 hover:text-ink"
                      aria-label={showPin ? "Hide PIN" : "Show PIN"}
                    >
                      {showPin ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                    </button>
                  </div>
                  <Buttonish busy={busy} disabled={lockLeft > 0 || pinMissing} />
                </div>
              </form>

              {error ? (
                <div className="mt-2 flex items-start gap-1.5 text-[11px] text-down">
                  <ShieldOff className="mt-0.5 h-3 w-3 shrink-0" />
                  <span>{error}</span>
                </div>
              ) : null}
              {lockLeft > 0 ? (
                <div className="mt-2 text-[10.5px] text-warn">
                  Locked for {lockLeft}s after too many wrong PINs.
                </div>
              ) : null}

              <p className="mt-3 text-[10px] leading-relaxed text-faint">
                Sessions last 12 hours and live in an HttpOnly cookie — the PIN itself is never stored in the
                browser or repeated in the URL.
              </p>
            </>
          )}
        </div>

        <p className="mt-3 text-center text-[10px] text-faint">
          {session.loopback
            ? "You are on the machine itself — sessions here skip the PIN."
            : "Protected by a per-role PIN. Rotate it with `asta pins set`."}
        </p>
      </div>
    </div>
  )
}

function Buttonish({ busy, disabled }: { busy: boolean; disabled: boolean }) {
  return (
    <button
      type="submit"
      disabled={busy || disabled}
      className={cn(
        "inline-flex h-10 cursor-pointer items-center gap-1.5 rounded-xl bg-info px-3.5 text-[12px] font-semibold text-white transition-opacity",
        "hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50",
      )}
    >
      {busy ? "Checking…" : "Unlock"}
      <ArrowRight className="h-3.5 w-3.5" />
    </button>
  )
}
