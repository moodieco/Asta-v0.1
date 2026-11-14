import * as React from "react"
import { createPortal } from "react-dom"
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button, IconButton } from "@/components/ui"

/* ================================================================== *
 * Toasts — success / error / info, used for every confirmable action
 * ================================================================== */

type ToastTone = "success" | "error" | "info" | "warning"

interface Toast {
  id: number
  tone: ToastTone
  title: string
  description?: string
}

interface ToastApi {
  push: (toast: Omit<Toast, "id">) => void
  success: (title: string, description?: string) => void
  error: (title: string, description?: string) => void
  info: (title: string, description?: string) => void
}

const ToastContext = React.createContext<ToastApi | null>(null)

let nextId = 1

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<Toast[]>([])

  const remove = React.useCallback((id: number) => {
    setToasts((list) => list.filter((t) => t.id !== id))
  }, [])

  const push = React.useCallback(
    (toast: Omit<Toast, "id">) => {
      const id = nextId++
      setToasts((list) => [...list, { ...toast, id }])
      window.setTimeout(() => remove(id), 5200)
    },
    [remove],
  )

  const api = React.useMemo<ToastApi>(
    () => ({
      push,
      success: (title, description) => push({ tone: "success", title, description }),
      error: (title, description) => push({ tone: "error", title, description }),
      info: (title, description) => push({ tone: "info", title, description }),
    }),
    [push],
  )

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[80] flex w-[320px] flex-col gap-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className="pointer-events-auto animate-rise rounded-xl border border-line bg-surface p-3 shadow-[var(--shadow-pop)]"
          >
            <div className="flex items-start gap-2.5">
              <span
                className={cn(
                  "mt-[1px] grid h-5 w-5 shrink-0 place-items-center rounded-full",
                  toast.tone === "success" && "bg-up-soft text-up",
                  toast.tone === "error" && "bg-down-soft text-down",
                  toast.tone === "warning" && "bg-warn-soft text-warn",
                  toast.tone === "info" && "bg-info-soft text-info",
                )}
              >
                {toast.tone === "success" ? (
                  <CheckCircle2 className="h-3.5 w-3.5" />
                ) : toast.tone === "error" ? (
                  <XCircle className="h-3.5 w-3.5" />
                ) : toast.tone === "warning" ? (
                  <AlertTriangle className="h-3.5 w-3.5" />
                ) : (
                  <Info className="h-3.5 w-3.5" />
                )}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-[12px] font-medium text-ink">{toast.title}</div>
                {toast.description ? (
                  <p className="mt-0.5 text-[11px] leading-relaxed text-faint">{toast.description}</p>
                ) : null}
              </div>
              <IconButton label="Dismiss" onClick={() => remove(toast.id)} className="h-5 w-5">
                <X className="h-3 w-3" />
              </IconButton>
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastApi {
  const context = React.useContext(ToastContext)
  if (!context) throw new Error("useToast must be used inside <ToastProvider>")
  return context
}

/* ================================================================== *
 * Modal + confirmation dialog
 * ================================================================== */

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  width = "max-w-[520px]",
}: {
  open: boolean
  onClose: () => void
  title: React.ReactNode
  description?: React.ReactNode
  children?: React.ReactNode
  footer?: React.ReactNode
  width?: string
}) {
  React.useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, onClose])

  if (!open) return null

  return createPortal(
    <div className="fixed inset-0 z-[90] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-[#101828]/30 backdrop-blur-[2px]" onClick={onClose} aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        className={cn(
          "relative w-full animate-rise overflow-hidden rounded-2xl border border-line bg-surface shadow-[var(--shadow-pop)]",
          width,
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-3.5">
          <div className="min-w-0">
            <h2 className="text-[13.5px] font-semibold tracking-tight text-ink">{title}</h2>
            {description ? (
              <p className="mt-0.5 text-[11.5px] leading-relaxed text-faint">{description}</p>
            ) : null}
          </div>
          <IconButton label="Close" onClick={onClose}>
            <X className="h-3.5 w-3.5" />
          </IconButton>
        </div>
        {children ? <div className="max-h-[62vh] overflow-y-auto px-5 py-4">{children}</div> : null}
        {footer ? (
          <div className="flex items-center justify-end gap-2 border-t border-line bg-surface-2 px-5 py-3">
            {footer}
          </div>
        ) : null}
      </div>
    </div>,
    document.body,
  )
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  tone = "danger",
  onConfirm,
  onCancel,
  busy = false,
  note,
}: {
  open: boolean
  title: string
  description?: React.ReactNode
  confirmLabel?: string
  cancelLabel?: string
  tone?: "danger" | "primary"
  onConfirm: () => void
  onCancel: () => void
  busy?: boolean
  note?: React.ReactNode
}) {
  return (
    <Modal
      open={open}
      onClose={onCancel}
      title={title}
      description={description}
      width="max-w-[440px]"
      footer={
        <>
          <Button variant="ghost" onClick={onCancel} disabled={busy}>
            {cancelLabel}
          </Button>
          <Button variant={tone === "danger" ? "danger" : "primary"} onClick={onConfirm} loading={busy}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <div className="flex items-start gap-2.5 rounded-xl border border-warn/25 bg-warn-soft/60 px-3 py-2.5">
        <AlertTriangle className="mt-[1px] h-3.5 w-3.5 shrink-0 text-warn" />
        <div className="text-[11.5px] leading-relaxed text-warn">
          {note ?? "This action is recorded in the preview layer only — the engine is not modified."}
        </div>
      </div>
    </Modal>
  )
}
