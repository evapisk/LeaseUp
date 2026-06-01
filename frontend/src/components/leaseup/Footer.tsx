export function Footer() {
  return (
    <footer className="relative border-t border-hairline">
      <div className="mx-auto max-w-6xl px-6 py-12">
        <div className="flex flex-col items-start justify-between gap-6 sm:flex-row sm:items-center">
          <div>
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-mint/15 ring-1 ring-mint/40">
                <span className="font-mono text-xs font-bold text-mint">S</span>
              </div>
              <span className="text-lg font-semibold tracking-tight">LeaseUp</span>
            </div>
            <p className="mt-3 max-w-md text-sm text-muted-foreground">
              An open look at NYC restaurant health inspections. Data: NYC DOHMH
              via NYC OpenData.
            </p>
          </div>
          <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
            <span className="text-mint">●</span> system online · v0.1
          </div>
        </div>
        <div className="mt-10 border-t border-hairline pt-6 font-mono text-[11px] text-muted-foreground">
          © {new Date().getFullYear()} LeaseUp — know before you go.
        </div>
      </div>
    </footer>
  );
}
