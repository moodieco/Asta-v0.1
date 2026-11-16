import { useEffect, useState } from "react"
import { Check, Copy, Link2, RefreshCw } from "lucide-react"
import { libraryActions, type ShareInfo } from "@/lib/library"
import { Badge, Button } from "@/components/ui"
import { Modal, useToast } from "@/components/feedback"

export function ShareDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const toast = useToast()
  const [info, setInfo] = useState<ShareInfo | null>(null)
  const [busy, setBusy] = useState(false)

  const load = () => {
    libraryActions
      .share()
      .then(setInfo)
      .catch(() => setInfo({ enabled: false }))
  }

  useEffect(() => {
    if (open) load()
  }, [open])

  const copy = (text: string, label: string) => {
    if (!text) return
    navigator.clipboard.writeText(text).then(
      () => toast.success(`${label} copied`),
      () => toast.error("Copy failed", "Select and copy the link manually."),
    )
  }

  const regenerate = async () => {
    setBusy(true)
    try {
      await libraryActions.regenerateShare()
      load()
      toast.success("Share links regenerated", "Old links no longer work.")
    } catch (error) {
      toast.error("Could not regenerate", error instanceof Error ? error.message : String(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Share the dashboard"
      description="Editor links can do everything; view-only links can read but not change anything."
      width="max-w-[560px]"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
          <Button variant="secondary" onClick={regenerate} loading={busy}>
            <RefreshCw className="h-3.5 w-3.5" /> Regenerate links
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        {!info?.enabled ? (
          <div className="rounded-xl border border-line bg-surface-2 px-3 py-2.5 text-[11.5px] text-faint">
            Sharing is unavailable while the engine is offline.
          </div>
        ) : (
          <>
            <LinkRow
              label="Editor link"
              tone="info"
              url={info.editorUrl ?? ""}
              hint="Full access — upload, uninstall, test alerts, change settings."
              onCopy={() => copy(info.editorUrl ?? "", "Editor link")}
            />
            <LinkRow
              label="View-only link"
              tone="mint"
              url={info.viewUrl ?? ""}
              hint="Read-only — signals, scanner status and history, no changes."
              onCopy={() => copy(info.viewUrl ?? "", "View-only link")}
            />
            <div className="rounded-xl border border-line bg-surface-2 px-3 py-2.5">
              <div className="text-[10px] uppercase tracking-wider text-faint">How it works</div>
              <p className="mt-1 text-[11px] leading-relaxed text-dim">
                The dashboard listens on <span className="font-mono">{info.host}:{info.port}</span> (bind{" "}
                <span className="font-mono">0.0.0.0</span>). On this machine it opens without a token; anyone else on
                {info.lanIps?.length ? (
                  <>
                    {" "}
                    the network (<span className="font-mono">{(info.lanIps ?? []).join(", ")}</span>)
                  </>
                ) : null}{" "}
                needs one of these links. Each link carries its own token in the URL.
              </p>
            </div>
          </>
        )}
      </div>
    </Modal>
  )
}

function LinkRow({
  label,
  tone,
  url,
  hint,
  onCopy,
}: {
  label: string
  tone: "info" | "mint"
  url: string
  hint: string
  onCopy: () => void
}) {
  const [copied, setCopied] = useState(false)
  return (
    <div className="rounded-xl border border-line-soft bg-surface-2 px-3 py-2.5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Badge tone={tone}>{label}</Badge>
        </div>
        <Button
          variant="secondary"
          onClick={() => {
            onCopy()
            setCopied(true)
            window.setTimeout(() => setCopied(false), 1600)
          }}
        >
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <div className="mt-1.5 flex items-center gap-1.5">
        <Link2 className="h-3 w-3 shrink-0 text-faint" />
        <span className="break-all font-mono text-[10.5px] text-dim">{url}</span>
      </div>
      <p className="mt-1 text-[10.5px] text-faint">{hint}</p>
    </div>
  )
}
