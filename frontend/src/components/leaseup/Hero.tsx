import { useEffect, useState } from "react";
import { ArrowRight, Radar } from "lucide-react";

export function Hero({ total = 27193 }: { total?: number }) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    const start = Date.now();
    const id = setInterval(() => {
      const t = Math.min(1, (Date.now() - start) / 1400);
      setCount(Math.round(total * t));
      if (t >= 1) clearInterval(id);
    }, 40);
    return () => clearInterval(id);
  }, [total]);

  return (
    <section className="relative overflow-hidden">
      <div className="absolute inset-0 grid-bg opacity-60" />
      <div className="absolute inset-0 scanlines" />
      <div className="pointer-events-none absolute inset-0">
        {Array.from({ length: 14 }).map((_, i) => (
          <span
            key={i}
            className="absolute block h-1 w-1 rounded-full bg-mint/60"
            style={{
              left: `${(i * 73) % 100}%`,
              bottom: "-10px",
              animation: `drift ${8 + (i % 5) * 1.4}s linear ${i * 0.6}s infinite`,
            }}
          />
        ))}
      </div>
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-mint/70 to-transparent"
        style={{ animation: "scanline-sweep 9s linear infinite" }}
      />

      <div className="relative mx-auto max-w-6xl px-6 pt-28 pb-32 sm:pt-36 sm:pb-44">
        <div className="inline-flex items-center gap-2 rounded-full hairline bg-surface/60 px-3 py-1.5 backdrop-blur animate-fade-up">
          <Radar className="h-3.5 w-3.5 text-mint animate-pulse-soft" />
          <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-mint">
            live signal · NYC health inspections
          </span>
        </div>

        <h1
          className="mt-6 max-w-4xl text-5xl font-bold tracking-tight text-foreground sm:text-7xl animate-fade-up"
          style={{ animationDelay: "60ms" }}
        >
          See which NYC kitchens{" "}
          <span className="text-mint text-glow">cut corners</span>{" "}
          before you order.
        </h1>

        <p
          className="mt-6 max-w-2xl text-lg text-muted-foreground sm:text-xl animate-fade-up"
          style={{ animationDelay: "160ms" }}
        >
          ScoutEats turns the city's health-inspection record into one calm feed —
          every flagged restaurant, its critical violations, and how recently the
          inspectors stopped by.
        </p>

        <div
          className="mt-10 flex flex-wrap items-center gap-4 animate-fade-up"
          style={{ animationDelay: "260ms" }}
        >
          <a
            href="#search"
            className="group inline-flex items-center gap-2 rounded-full bg-mint px-6 py-3 text-sm font-semibold text-mint-foreground transition-all hover:gap-3 hover:shadow-[0_0_40px_-5px_oklch(0.88_0.18_170/0.6)]"
          >
            Start scanning
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </a>
          <a
            href="#about"
            className="inline-flex items-center gap-2 rounded-full hairline bg-surface/40 px-6 py-3 text-sm font-medium text-foreground/90 backdrop-blur hover:bg-surface/70"
          >
            How it works
          </a>
        </div>

        <div
          className="mt-14 flex items-center gap-3 font-mono text-xs text-muted-foreground animate-fade-up"
          style={{ animationDelay: "360ms" }}
        >
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-mint/70" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-mint" />
          </span>
          <span>
            <span className="text-foreground">{count.toLocaleString()}</span> restaurants tracked
            across <span className="text-foreground">5</span> boroughs
          </span>
        </div>
      </div>
    </section>
  );
}
