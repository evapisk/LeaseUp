import { ExternalLink, Ban, ShieldAlert, AlertCircle } from "lucide-react";
import type { Listing, RiskLevel } from "@/data/listings";
import { RISK_LABELS } from "@/data/listings";
import { useEnrichCard } from "@/hooks/useEnrichCard";
import type { TakeoverStep, TakeoverStepCategory } from "@/lib/api/enrich";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";

const RISK_TONE: Record<RiskLevel, string> = {
  high: "bg-urgent/15 text-urgent ring-1 ring-urgent/40",
  medium: "bg-warn/15 text-warn ring-1 ring-warn/40",
  low: "bg-mint/10 text-mint ring-1 ring-mint/30",
};

const STEP_TONE: Record<TakeoverStepCategory, string> = {
  remediation: "bg-coral/10 text-coral ring-coral/30",
  permit: "bg-mint/10 text-mint ring-mint/30",
  inspection: "bg-warn/10 text-warn ring-warn/30",
  legal: "bg-primary/10 text-primary ring-primary/30",
  financial: "bg-mint/10 text-mint ring-mint/30",
  general: "bg-muted text-muted-foreground ring-border",
};

export function TakeoverModal({
  listing,
  open,
  onOpenChange,
}: {
  listing: Listing;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { data, isLoading, isError } = useEnrichCard(listing, open);

  const headline = data?.takeover.headline ?? `Steps to take over ${listing.name}`;
  const risk = data?.card.summary.risk ?? listing.risk;
  const isClosed = data?.card.summary.is_closed ?? Boolean(listing.is_closed);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl gap-0 overflow-hidden p-0">
        <DialogHeader className="space-y-3 p-6 pb-4">
          <DialogTitle className="pr-8 text-xl">{headline}</DialogTitle>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-[11px] font-medium ${RISK_TONE[risk]}`}
            >
              <ShieldAlert className="h-3 w-3" />
              {RISK_LABELS[risk]}
            </span>
            {isClosed && (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-urgent px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider text-background">
                <Ban className="h-3 w-3" />
                Closed by DOHMH
              </span>
            )}
            <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              CAMIS {listing.id}
            </span>
          </div>
          {data && (
            <DialogDescription className="text-left">
              {data.takeover.summary}
            </DialogDescription>
          )}
        </DialogHeader>

        <div className="border-t border-hairline">
          {isLoading && <LoadingBody />}
          {isError && !data && (
            <div className="flex items-start gap-3 p-6 text-sm text-muted-foreground">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-warn" />
              <p>
                Could not build a takeover plan for this restaurant right now.
                Please close this dialog and try again.
              </p>
            </div>
          )}
          {data && (
            <ScrollArea className="max-h-[50vh]">
              <ol className="space-y-3 p-6">
                {data.takeover.steps.map((step) => (
                  <StepRow key={step.order} step={step} />
                ))}
              </ol>
            </ScrollArea>
          )}
        </div>

        <DialogFooter className="flex-col gap-3 border-t border-hairline p-6 sm:flex-row sm:items-center sm:justify-between">
          {data?.enrichment.degraded && (
            <p className="text-[11px] text-muted-foreground">
              AI assessment unavailable — steps derived locally.
            </p>
          )}
          <Button asChild className="sm:ml-auto">
            <a
              href={data?.takeover.codify_url ?? `https://codify.cafe/restaurants/${listing.id}`}
              target="_blank"
              rel="noreferrer"
            >
              View more on codify.cafe
              <ExternalLink className="h-4 w-4" />
            </a>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function StepRow({ step }: { step: TakeoverStep }) {
  const tone = step.category ? STEP_TONE[step.category] : STEP_TONE.general;
  return (
    <li className="flex gap-3 rounded-xl hairline bg-surface/50 p-4">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-mint/15 font-mono text-sm font-bold text-mint">
        {step.order}
      </span>
      <div className="min-w-0 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <h4 className="text-sm font-semibold text-foreground">{step.title}</h4>
          {step.category && (
            <Badge
              variant="outline"
              className={`rounded-full px-2 py-0 text-[10px] uppercase tracking-wider ring-1 ${tone}`}
            >
              {step.category}
            </Badge>
          )}
        </div>
        <p className="text-sm text-muted-foreground">{step.detail}</p>
      </div>
    </li>
  );
}

function LoadingBody() {
  return (
    <div className="space-y-3 p-6">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="flex gap-3 rounded-xl hairline bg-surface/50 p-4">
          <Skeleton className="h-7 w-7 shrink-0 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-4/5" />
          </div>
        </div>
      ))}
    </div>
  );
}
