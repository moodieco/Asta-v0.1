import { useMemo, useRef, useState } from "react"
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  FileArchive,
  FileCode2,
  FileUp,
  Info,
  Loader2,
  PackageCheck,
  ShieldCheck,
  UploadCloud,
  X,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { fmtBytes, type AppData } from "@/lib/api"
import { libraryActions, type LibraryScanner } from "@/lib/library"
import type { Market } from "@/lib/preview"
import {
  Badge,
  Button,
  Card,
  CardHeader,
  CheckRow,
  Field,
  Input,
  PreviewChip,
  Progress,
  Textarea,
} from "@/components/ui"
import { ConfirmDialog, useToast } from "@/components/feedback"
import { PageHeader, Notice } from "@/components/layout"

type Step = 1 | 2 | 3 | 4 | 5
type Outcome = "success" | "error" | null

const TIMEFRAMES = ["5m", "15m", "30m", "1h", "4h", "1d"]
const MAX_BYTES = 25 * 1024 * 1024
const MARKET_PREFIX: Record<Market, string> = { stock: "STS", crypto: "CXS", forex: "FXS" }

interface FileInfo {
  name: string
  size: number
  type: string
  hash: string
  ext: string
}

interface ValidationCheck {
  id: string
  label: string
  ok: boolean
  detail: string
  severity: "error" | "warning"
}

const STEP_LABELS = ["Upload file", "Validate", "Review", "Install", "Done"]

export function UploadScannerPage({ data, navigate }: { data: AppData; navigate: (path: string) => void }) {
  const toast = useToast()
  const inputRef = useRef<HTMLInputElement | null>(null)

  const [step, setStep] = useState<Step>(1)
  const [dragging, setDragging] = useState(false)
  const [file, setFile] = useState<FileInfo | null>(null)
  const [reading, setReading] = useState(false)
  const [name, setName] = useState("")
  const [market, setMarket] = useState<Market>("crypto")
  const [version, setVersion] = useState("0.1.0")
  const [description, setDescription] = useState("")
  const [timeframes, setTimeframes] = useState<string[]>(["1h"])
  const [dependencies, setDependencies] = useState("asta-core>=0.1")
  const [checks, setChecks] = useState<ValidationCheck[] | null>(null)
  const [validating, setValidating] = useState(false)
  const [installing, setInstalling] = useState(false)
  const [installPct, setInstallPct] = useState(0)
  const [outcome, setOutcome] = useState<Outcome>(null)
  const [confirmCancel, setConfirmCancel] = useState(false)
  const [installed, setInstalled] = useState<LibraryScanner | null>(null)
  const [fileObj, setFileObj] = useState<File | null>(null)

  const dirty = Boolean(file || name || description)

  /* -------------------------------------------------- file handling */

  const acceptFile = async (incoming: File) => {
    if (incoming.size > MAX_BYTES) {
      toast.error("File too large", `Bundles must stay under ${fmtBytes(MAX_BYTES)}.`)
      return
    }
    setReading(true)
    let hash = "—"
    try {
      const buffer = await incoming.arrayBuffer()
      const digest = await crypto.subtle.digest("SHA-256", buffer)
      hash = [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 16)
    } catch {
      hash = "unavailable"
    }
    const ext = incoming.name.includes(".") ? incoming.name.split(".").pop()!.toLowerCase() : ""
    setFile({
      name: incoming.name,
      size: incoming.size,
      type: incoming.type || "application/octet-stream",
      hash,
      ext,
    })
    setFileObj(incoming)
    if (!name) {
      setName(
        incoming.name
          .replace(/\.(py|zip|tar\.gz)$/i, "")
          .replace(/[_-]+/g, " ")
          .replace(/\b\w/g, (c) => c.toUpperCase()),
      )
    }
    setChecks(null)
    setReading(false)
  }

  const onDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragging(false)
    const dropped = event.dataTransfer.files?.[0]
    if (dropped) void acceptFile(dropped)
  }

  /* -------------------------------------------------- validation */

  const runValidation = () => {
    setValidating(true)
    setChecks(null)
    window.setTimeout(() => {
      setChecks(buildChecks({ file, name, market, version, timeframes, description, dependencies }))
      setValidating(false)
      setStep(2)
    }, 900)
  }

  const errors = useMemo(() => (checks ?? []).filter((check) => !check.ok && check.severity === "error"), [checks])
  const warnings = useMemo(
    () => (checks ?? []).filter((check) => !check.ok && check.severity === "warning"),
    [checks],
  )

  /* -------------------------------------------------- install */

  const install = async () => {
    if (!file || !fileObj) return
    setStep(4)
    setInstalling(true)
    setInstallPct(10)
    try {
      let source: string
      if (file.ext === "zip") {
        const buffer = await fileObj.arrayBuffer()
        const bytes = new Uint8Array(buffer)
        let binary = ""
        for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i])
        source = btoa(binary)
      } else {
        source = await fileObj.text()
      }
      const deps = dependencies
        .split(/[\n,]/)
        .map((item) => item.trim())
        .filter(Boolean)

      setInstallPct(45)
      const { record } = await libraryActions.install({
        name: name.trim(),
        market,
        version: version.trim(),
        timeframes,
        description: description.trim(),
        dependencies: deps,
        changes: ["Uploaded through the dashboard installer"],
        source,
        sourceName: file.name,
        sha256: file.hash,
      })
      setInstallPct(100)
      setInstalled(record)
      setInstalling(false)
      setOutcome("success")
      setStep(5)
      toast.success("Scanner installed", `${record.name} is registered as ${record.scannerId}. Restart the engine to activate it.`)
    } catch (error) {
      setInstalling(false)
      setOutcome("error")
      setStep(5)
      toast.error("Installation failed", error instanceof Error ? error.message : String(error))
    }
  }

  const reset = () => {
    setStep(1)
    setFile(null)
    setName("")
    setVersion("0.1.0")
    setDescription("")
    setTimeframes(["1h"])
    setDependencies("asta-core>=0.1")
    setChecks(null)
    setOutcome(null)
    setInstalled(null)
    setInstallPct(0)
  }

  const canContinue = Boolean(file && name.trim() && version.trim() && timeframes.length)

  return (
    <div className="animate-rise">
      <PageHeader
        back="Scanner management"
        onBack={() => navigate("/scanners")}
        title="Upload scanner"
        description="Drop a bundle, validate it locally, review the manifest and install. The bundle is written to the scanner library and picked up by the engine on its next restart."
        badge={<Badge tone="warn">Coming soon</Badge>}
        actions={
          dirty ? (
            <Button variant="ghost" onClick={() => setConfirmCancel(true)}>
              <X className="h-3.5 w-3.5" /> Cancel
            </Button>
          ) : null
        }
      />

      <Notice tone="warn" title="Coming soon — installing is paused">
        The installer is being rebuilt around a single-file scanner template: metadata, params and the strategy
        live in one <code className="rounded bg-warn-soft px-1">scanner.py</code>, so a scanner can be read,
        reviewed and shared as one file. The flow below still shows what a bundle needs; the final install step is
        disabled until the template ships.
      </Notice>

      <Stepper step={step} />

      <div className="grid gap-3 xl:grid-cols-3">
        <div className="space-y-3 xl:col-span-2">
          {step === 1 ? (
            <>
              <Card>
                <CardHeader
                  title="1 · Upload the scanner bundle"
                  subtitle="Python module (.py) or bundled archive (.zip) up to 25 MB"
                />
                <div className="px-4 pb-4">
                  <div
                    onDragOver={(event) => {
                      event.preventDefault()
                      setDragging(true)
                    }}
                    onDragLeave={() => setDragging(false)}
                    onDrop={onDrop}
                    onClick={() => inputRef.current?.click()}
                    className={cn(
                      "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-9 text-center transition-colors",
                      dragging
                        ? "border-info/50 bg-info-soft/50"
                        : "border-line bg-surface-2 hover:border-info/30 hover:bg-info-soft/20",
                    )}
                  >
                    <span className="grid h-11 w-11 place-items-center rounded-xl bg-info-soft text-info">
                      <UploadCloud className="h-5 w-5" />
                    </span>
                    <div className="text-[12.5px] font-medium text-ink">
                      Drag and drop the file here
                    </div>
                    <p className="text-[11px] text-faint">
                      or <span className="font-medium text-info">browse files</span> — .py, .zip
                    </p>
                    <input
                      ref={inputRef}
                      type="file"
                      accept=".py,.zip"
                      className="hidden"
                      onChange={(event) => {
                        const picked = event.target.files?.[0]
                        if (picked) void acceptFile(picked)
                      }}
                    />
                  </div>

                  {reading ? (
                    <div className="mt-3 flex items-center gap-2 rounded-xl border border-line bg-surface-2 px-3 py-2 text-[11.5px] text-faint">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" /> Reading file and hashing…
                    </div>
                  ) : file ? (
                    <div className="mt-3 flex items-start gap-2.5 rounded-xl border border-line bg-surface-2 px-3 py-2.5">
                      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-violet-soft text-violet">
                        {file.ext === "zip" ? <FileArchive className="h-4 w-4" /> : <FileCode2 className="h-4 w-4" />}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-[11.5px] font-medium text-ink">{file.name}</div>
                        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px] text-faint">
                          <span className="tabnum">{fmtBytes(file.size)}</span>
                          <span>·</span>
                          <span>{file.type}</span>
                          <span>·</span>
                          <span className="font-mono">sha256 {file.hash}</span>
                        </div>
                      </div>
                      <button
                        onClick={(event) => {
                          event.stopPropagation()
                          setFile(null)
                          setChecks(null)
                        }}
                        className="cursor-pointer text-faint hover:text-down"
                        aria-label="Remove file"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ) : null}
                </div>
              </Card>

              <Card>
                <CardHeader title="Scanner information" subtitle="What the engine registers after install" />
                <div className="grid gap-3 px-4 pb-4 sm:grid-cols-2">
                  <Field label="Scanner name" required>
                    <Input value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. EMA Pullback" />
                  </Field>
                  <Field label="Market" required hint="The scanner id prefix follows the market (STS / CXS / FXS).">
                    <div className="flex gap-1">
                      {(["stock", "crypto", "forex"] as Market[]).map((option) => (
                        <button
                          key={option}
                          onClick={() => setMarket(option)}
                          className={cn(
                            "flex-1 cursor-pointer rounded-lg border px-2 py-1.5 text-[11.5px] font-medium capitalize transition-colors",
                            market === option
                              ? "border-info/30 bg-info-soft text-info"
                              : "border-line bg-surface text-dim hover:text-ink",
                          )}
                        >
                          {option === "stock" ? "Stocks" : option}
                        </button>
                      ))}
                    </div>
                  </Field>
                  <Field label="Scanner version" required hint="Semantic version, e.g. 1.2.0.">
                    <Input value={version} onChange={(event) => setVersion(event.target.value)} placeholder="0.1.0" />
                  </Field>
                  <Field label="Dependencies" hint="Comma or newline separated; checked by the installer.">
                    <Input value={dependencies} onChange={(event) => setDependencies(event.target.value)} />
                  </Field>
                  <Field label="Supported timeframes" required className="sm:col-span-2">
                    <div className="flex flex-wrap gap-1.5">
                      {TIMEFRAMES.map((tf) => {
                        const active = timeframes.includes(tf)
                        return (
                          <button
                            key={tf}
                            onClick={() =>
                              setTimeframes((current) =>
                                current.includes(tf) ? current.filter((item) => item !== tf) : [...current, tf],
                              )
                            }
                            className={cn(
                              "cursor-pointer rounded-lg border px-2.5 py-1 text-[11.5px] font-medium transition-colors",
                              active
                                ? "border-info/30 bg-info-soft text-info"
                                : "border-line bg-surface text-faint hover:text-ink",
                            )}
                          >
                            {tf}
                          </button>
                        )
                      })}
                    </div>
                  </Field>
                  <Field label="Description" className="sm:col-span-2" hint="Shown in scanner management and the detail page.">
                    <Textarea
                      value={description}
                      onChange={(event) => setDescription(event.target.value)}
                      placeholder="What the scanner looks for, in one or two sentences."
                    />
                  </Field>
                </div>
              </Card>

              <div className="flex flex-wrap items-center justify-end gap-2">
                <Button variant="ghost" onClick={() => setConfirmCancel(true)} disabled={!dirty}>
                  Cancel
                </Button>
                <Button variant="primary" size="md" onClick={runValidation} disabled={!canContinue} loading={validating}>
                  Validate scanner
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </div>
            </>
          ) : null}

          {step === 2 ? (
            <>
              <Card>
                <CardHeader
                  title="2 · Validation"
                  subtitle="Local checks only — the engine re-validates the manifest on install"
                  right={
                    validating ? (
                      <Badge tone="info">running</Badge>
                    ) : errors.length ? (
                      <Badge tone="down">{errors.length} blocking</Badge>
                    ) : (
                      <Badge tone="up">ready</Badge>
                    )
                  }
                />
                <div className="px-4 pb-4">
                  {validating || !checks ? (
                    <div className="flex items-center gap-2 rounded-xl border border-line bg-surface-2 px-3 py-3 text-[11.5px] text-faint">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" /> Running bundle, manifest and compatibility checks…
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {checks.map((check) => (
                        <div
                          key={check.id}
                          className="rounded-xl border border-line-soft bg-surface-2 px-3 py-2"
                        >
                          <CheckRow ok={check.ok} severity={check.severity}>{check.label}</CheckRow>
                          <div className="mt-0.5 pl-6 text-[10px] text-faint">{check.detail}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </Card>

              <div className="flex flex-wrap items-center justify-between gap-2">
                <Button variant="secondary" onClick={() => setStep(1)}>
                  <ArrowLeft className="h-3.5 w-3.5" /> Back
                </Button>
                <Button
                  variant="primary"
                  size="md"
                  onClick={() => setStep(3)}
                  disabled={!checks || validating || errors.length > 0}
                >
                  Review scanner
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </div>
            </>
          ) : null}

          {step === 3 ? (
            <>
              <Card>
                <CardHeader title="3 · Review" subtitle="Exactly what will be registered" />
                <div className="px-4 pb-4">
                  <div className="grid gap-2 sm:grid-cols-2">
                    {[
                      ["Scanner name", name],
                      ["Market", market === "stock" ? "Stocks" : market],
                      ["Version", version],
                      ["Bundle", file?.name ?? "—"],
                      ["Bundle size", fmtBytes(file?.size)],
                      ["Bundle hash", file?.hash ?? "—"],
                      ["Timeframes", timeframes.join(", ") || "—"],
                      ["Dependencies", dependencies || "none"],
                    ].map(([label, value]) => (
                      <div key={label} className="rounded-xl border border-line-soft bg-surface-2 px-3 py-2">
                        <div className="text-[10px] uppercase tracking-wider text-faint">{label}</div>
                        <div className="mt-0.5 break-words text-[11.5px] text-ink">{value}</div>
                      </div>
                    ))}
                  </div>
                  {description ? (
                    <div className="mt-2 rounded-xl border border-line-soft bg-surface-2 px-3 py-2">
                      <div className="text-[10px] uppercase tracking-wider text-faint">Description</div>
                      <p className="mt-0.5 text-[11.5px] leading-relaxed text-dim">{description}</p>
                    </div>
                  ) : null}
                  {warnings.length ? (
                    <div className="mt-2 rounded-xl border border-warn/25 bg-warn-soft/60 px-3 py-2">
                      <div className="flex items-center gap-1.5 text-[11px] font-medium text-warn">
                        <AlertTriangle className="h-3 w-3" /> {warnings.length} warning{warnings.length > 1 ? "s" : ""}
                      </div>
                      <ul className="mt-1 space-y-0.5">
                        {warnings.map((warning) => (
                          <li key={warning.id} className="text-[10.5px] leading-relaxed text-warn/90">
                            · {warning.detail}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              </Card>

              <div className="flex flex-wrap items-center justify-between gap-2">
                <Button variant="secondary" onClick={() => setStep(2)}>
                  <ArrowLeft className="h-3.5 w-3.5" /> Back to validation
                </Button>
                <Button variant="primary" size="md" onClick={install} disabled title="Coming soon">
                  Install scanner (coming soon)
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </div>
            </>
          ) : null}

          {step === 4 ? (
            <Card>
              <CardHeader title="4 · Installing" subtitle="Registering the bundle with the scanner library" />
              <div className="px-4 pb-4">
                <Progress pct={installPct} />
                <div className="mt-2 flex items-center justify-between text-[11px] text-faint">
                  <span>{installPct < 35 ? "Copying bundle…" : installPct < 70 ? "Writing manifest…" : "Registering scanner…"}</span>
                  <span className="tabnum">{Math.round(installPct)}%</span>
                </div>
                <div className="mt-3 space-y-1.5">
                  {[
                    "Bundle accepted",
                    "Manifest parsed",
                    "Compatibility confirmed",
                    "Scanner registered",
                  ].map((label, index) => {
                    const done = installPct >= (index + 1) * 24
                    return (
                      <div key={label} className="flex items-center gap-2 text-[11px]">
                        <span
                          className={cn(
                            "grid h-4 w-4 place-items-center rounded-full",
                            done ? "bg-up-soft text-up" : "bg-surface-3 text-faint",
                          )}
                        >
                          {done ? <CheckCircle2 className="h-2.5 w-2.5" /> : <Loader2 className="h-2.5 w-2.5 animate-spin" />}
                        </span>
                        <span className={done ? "text-dim" : "text-faint"}>{label}</span>
                      </div>
                    )
                  })}
                </div>
                {installing ? null : (
                  <p className="mt-3 text-[10.5px] text-faint">Finishing…</p>
                )}
              </div>
            </Card>
          ) : null}

          {step === 5 ? (
            <Card>
              <CardHeader title="5 · Result" subtitle="Installer outcome" />
              <div className="px-4 pb-4">
                {outcome === "success" && installed ? (
                  <div className="rounded-xl border border-up/20 bg-up-soft/40 px-4 py-5 text-center">
                    <span className="mx-auto grid h-11 w-11 place-items-center rounded-full bg-up text-white">
                      <PackageCheck className="h-5 w-5" />
                    </span>
                    <div className="mt-2 text-[13.5px] font-semibold text-ink">{installed.name} installed</div>
                    <p className="mx-auto mt-1 max-w-sm text-[11.5px] leading-relaxed text-faint">
                      Registered as <span className="font-mono text-dim">{installed.scannerId}</span> · v
                      {installed.version} · {installed.timeframes.join(", ")}. The engine picks it up on the next
                      restart.
                    </p>
                    <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
                      <Button variant="primary" onClick={() => navigate("/scanners")}>
                        View in scanner management
                      </Button>
                      <Button variant="secondary" onClick={() => navigate("/uploads")}>
                        Upload history
                      </Button>
                      <Button variant="ghost" onClick={reset}>
                        Upload another
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-xl border border-down/20 bg-down-soft/40 px-4 py-5 text-center">
                    <span className="mx-auto grid h-11 w-11 place-items-center rounded-full bg-down text-white">
                      <AlertTriangle className="h-5 w-5" />
                    </span>
                    <div className="mt-2 text-[13.5px] font-semibold text-ink">Installation failed</div>
                    <p className="mx-auto mt-1 max-w-sm text-[11.5px] leading-relaxed text-faint">
                      The scanner could not be registered. Review the validation output and try again.
                    </p>
                    <div className="mt-3 flex items-center justify-center gap-2">
                      <Button variant="secondary" onClick={() => setStep(2)}>
                        Back to validation
                      </Button>
                      <Button variant="primary" onClick={reset}>
                        Start over
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </Card>
          ) : null}
        </div>

        <div className="space-y-3">
          <Card>
            <CardHeader title="Bundle requirements" subtitle="Checked before install" right={<ShieldCheck className="h-3.5 w-3.5 text-faint" />} />
            <div className="space-y-1.5 px-4 pb-4 text-[11px] leading-relaxed text-faint">
              {[
                "File must be .py or .zip, under 25 MB",
                "Scanner name and semantic version are required",
                "Scanner id prefix must match the market",
                "At least one supported timeframe",
                "Dependencies must resolve against core",
              ].map((rule) => (
                <div key={rule} className="flex items-start gap-1.5">
                  <CheckCircle2 className="mt-[2px] h-3 w-3 shrink-0 text-faint" />
                  <span>{rule}</span>
                </div>
              ))}
            </div>
          </Card>

          <Card>
            <CardHeader title="What happens on install" subtitle="No trading execution is involved" />
            <div className="space-y-2 px-4 pb-4 text-[11px] leading-relaxed text-dim">
              <div className="flex gap-2">
                <FileUp className="mt-[2px] h-3.5 w-3.5 shrink-0 text-info" />
                The bundle is copied into the scanner library and registered with its market and timeframes.
              </div>
              <div className="flex gap-2">
                <Info className="mt-[2px] h-3.5 w-3.5 shrink-0 text-info" />
                The engine picks the scanner up on its next restart, then signals flow to Signal History as usual.
              </div>
              <div className="flex gap-2">
                <AlertTriangle className="mt-[2px] h-3.5 w-3.5 shrink-0 text-warn" />
                Deleting a scanner moves it to the recycle bin — nothing is erased until you purge it.
              </div>
            </div>
          </Card>

          <Notice tone="info" title="Scanner library">
            Uploads land in <span className="font-mono">data/scanners/&lt;market&gt;/&lt;ID&gt;/</span> and appear in
            Scanner Management immediately; the engine activates them on restart.
          </Notice>
        </div>
      </div>

      <ConfirmDialog
        open={confirmCancel}
        title="Discard this upload?"
        description="The file reference, manifest fields and validation output are discarded."
        confirmLabel="Discard"
        onConfirm={() => {
          setConfirmCancel(false)
          reset()
          toast.info("Upload discarded")
        }}
        onCancel={() => setConfirmCancel(false)}
      />
    </div>
  )
}

function Stepper({ step }: { step: Step }) {
  return (
    <Card className="mb-3 px-4 py-3">
      <div className="flex items-center gap-1 overflow-x-auto">
        {STEP_LABELS.map((label, index) => {
          const number = index + 1
          const active = step === number
          const done = step > number
          return (
            <div key={label} className="flex flex-1 items-center gap-1 last:flex-none">
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    "grid h-6 w-6 shrink-0 place-items-center rounded-full text-[10.5px] font-semibold",
                    done
                      ? "bg-up-soft text-up"
                      : active
                        ? "bg-info text-white"
                        : "bg-surface-3 text-faint",
                  )}
                >
                  {done ? <CheckCircle2 className="h-3 w-3" /> : number}
                </span>
                <span
                  className={cn(
                    "whitespace-nowrap text-[11.5px] font-medium",
                    active ? "text-ink" : done ? "text-dim" : "text-faint",
                  )}
                >
                  {label}
                </span>
              </div>
              {index < STEP_LABELS.length - 1 ? (
                <div className={cn("mx-1 h-[2px] flex-1 rounded-full", done ? "bg-up/40" : "bg-line")} />
              ) : null}
            </div>
          )
        })}
      </div>
    </Card>
  )
}

function buildChecks({
  file,
  name,
  market,
  version,
  timeframes,
  description,
  dependencies,
}: {
  file: FileInfo | null
  name: string
  market: Market
  version: string
  timeframes: string[]
  description: string
  dependencies: string
}): ValidationCheck[] {
  const checks: ValidationCheck[] = []
  const semver = /^\d+\.\d+\.\d+([+-][\w.]+)?$/
  const prefix = MARKET_PREFIX[market]

  checks.push({
    id: "file",
    label: "Bundle file present and readable",
    ok: Boolean(file),
    detail: file ? `${file.name} · ${fmtBytes(file.size)} · sha256 ${file.hash}` : "No file selected.",
    severity: "error",
  })
  checks.push({
    id: "type",
    label: "Bundle type supported",
    ok: Boolean(file && ["py", "zip"].includes(file.ext)),
    detail: file ? `.${file.ext} ${["py", "zip"].includes(file.ext) ? "is accepted" : "is not supported"}` : "—",
    severity: "error",
  })
  checks.push({
    id: "size",
    label: "Bundle size within limits",
    ok: Boolean(file && file.size > 0 && file.size <= MAX_BYTES),
    detail: file ? `${fmtBytes(file.size)} of ${fmtBytes(MAX_BYTES)} max` : "—",
    severity: "error",
  })
  checks.push({
    id: "name",
    label: "Scanner name provided",
    ok: name.trim().length >= 3,
    detail: name.trim() ? `"${name.trim()}"` : "At least 3 characters.",
    severity: "error",
  })
  checks.push({
    id: "version",
    label: "Version follows semantic versioning",
    ok: semver.test(version.trim()),
    detail: version.trim() ? `v${version.trim()}` : "e.g. 1.2.0",
    severity: "error",
  })
  checks.push({
    id: "timeframes",
    label: "At least one supported timeframe",
    ok: timeframes.length > 0,
    detail: timeframes.length ? timeframes.join(", ") : "Select a timeframe.",
    severity: "error",
  })
  const expectedPrefix = `${prefix}S`
  checks.push({
    id: "market",
    label: `Scanner id prefix matches ${market}`,
    ok: true,
    detail: `Will be registered under ${expectedPrefix}### — the id is derived from the market`,
    severity: "warning",
  })
  checks.push({
    id: "deps",
    label: "Dependencies declared",
    ok: dependencies.trim().length > 0,
    detail: dependencies.trim() || "No dependencies declared — the installer will not resolve core.",
    severity: "warning",
  })
  checks.push({
    id: "description",
    label: "Description helps operators",
    ok: description.trim().length >= 20,
    detail: description.trim()
      ? `${description.trim().length} characters`
      : "Short descriptions are allowed but make the scanner harder to audit.",
    severity: "warning",
  })
  return checks
}
