import { useState } from "react"
import { Recycle, RotateCcw, Trash2 } from "lucide-react"
import { fmtBytes } from "@/lib/api"
import { fmtDateTime, relTime } from "@/lib/format"
import { libraryActions, useLibrary, type TrashItem } from "@/lib/library"
import { marketMeta } from "@/lib/scanners"
import { Badge, Button, Card, EmptyState, Td, Th, Tr } from "@/components/ui"
import { ConfirmDialog, useToast } from "@/components/feedback"
import { PageHeader, Notice } from "@/components/layout"

export function RecycleBinPage({ navigate }: { navigate: (path: string) => void }) {
  const { library, refresh } = useLibrary()
  const toast = useToast()
  const [confirm, setConfirm] = useState<{ kind: "restore" | "purge"; item: TrashItem } | null>(null)
  const [busy, setBusy] = useState(false)

  const run = async () => {
    if (!confirm) return
    setBusy(true)
    try {
      if (confirm.kind === "restore") {
        await libraryActions.restore(confirm.item.scannerId)
        toast.success(`${confirm.item.name} restored`, "Back in Scanner Management. Restart the engine to activate.")
      } else {
        await libraryActions.purge(confirm.item.scannerId)
        toast.success(`${confirm.item.name} permanently deleted`)
      }
      refresh()
    } catch (error) {
      toast.error("Action failed", error instanceof Error ? error.message : String(error))
    } finally {
      setBusy(false)
      setConfirm(null)
    }
  }

  return (
    <div className="animate-rise">
      <PageHeader
        back="Scanner management"
        onBack={() => navigate("/scanners")}
        title="Recycle bin"
        description="Deleted scanners wait here instead of being erased. Restore them, or delete permanently."
        badge={
          <>
            <Badge tone="warn">Coming soon</Badge>
            <Badge tone="neutral">{library.trash.length} deleted</Badge>
          </>
        }
      />

      <Notice tone="warn" title="Coming soon — restore and purge are paused">
        The recycle bin is being reworked together with the single-file scanner template. Deleted bundles stay on disk
        exactly as they are; restoring and permanent deletion are disabled until that ships.
      </Notice>

      <Notice tone="info" title="Where deleted scanners go">
        Uninstalling a scanner moves its folder into{" "}
        <span className="font-mono">{library.trashRoot || "data/scanners/.trash/"}</span>. Nothing is erased until you
        choose &ldquo;Delete permanently&rdquo;.
      </Notice>

      <Card className="overflow-hidden">
        {library.trash.length === 0 ? (
          <div className="p-4">
            <EmptyState
              icon={<Recycle className="h-4 w-4" />}
              title="Recycle bin is empty"
              description="Scanners you uninstall from Scanner Management land here so they can be restored."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead>
                <tr>
                  <Th>Scanner name</Th>
                  <Th>Market</Th>
                  <Th>Version</Th>
                  <Th>Deleted</Th>
                  <Th>Reason</Th>
                  <Th align="right">Bundle</Th>
                  <Th align="right">Actions</Th>
                </tr>
              </thead>
              <tbody>
                {library.trash.map((item) => (
                  <Tr key={item.scannerId}>
                    <Td>
                      <div className="font-medium text-ink">{item.name}</div>
                      <div className="font-mono text-[10px] text-faint">{item.scannerId}</div>
                    </Td>
                    <Td>
                      <Badge tone={marketMeta(item.market).tone}>{marketMeta(item.market).label}</Badge>
                    </Td>
                    <Td className="tabnum">v{item.version}</Td>
                    <Td className="whitespace-nowrap" title={fmtDateTime(item.deletedAt)}>
                      {relTime(item.deletedAt)}
                    </Td>
                    <Td className="max-w-[220px] truncate text-[11px] text-faint">{item.deletedReason}</Td>
                    <Td align="right" className="tabnum text-faint">
                      {fmtBytes(item.sizeBytes)}
                    </Td>
                    <Td align="right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="secondary"
                          onClick={() => setConfirm({ kind: "restore", item })}
                          disabled
                          title="Coming soon"
                        >
                          <RotateCcw className="h-3.5 w-3.5" /> Restore
                        </Button>
                        <Button
                          variant="ghost"
                          onClick={() => setConfirm({ kind: "purge", item })}
                          className="text-faint hover:text-down"
                          disabled
                          title="Coming soon"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <ConfirmDialog
        open={confirm !== null}
        busy={busy}
        title={
          confirm?.kind === "restore"
            ? `Restore ${confirm?.item.name ?? ""}?`
            : `Permanently delete ${confirm?.item.name ?? ""}?`
        }
        description={
          confirm?.kind === "restore"
            ? "The scanner returns to Scanner Management. The engine activates it on the next restart."
            : "This erases the scanner bundle from the recycle bin for good. There is no undo."
        }
        confirmLabel={confirm?.kind === "restore" ? "Restore" : "Delete permanently"}
        tone={confirm?.kind === "restore" ? "primary" : "danger"}
        onConfirm={run}
        onCancel={() => setConfirm(null)}
      />
    </div>
  )
}
