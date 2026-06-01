import { Bug, Flag, Thermometer } from "lucide-react";
import { useInView } from "@/hooks/useInView";

const PROPS = [
  {
    icon: Flag,
    title: "Every violation, counted",
    body: "We total each restaurant's violations and flag the critical ones that put diners at risk.",
  },
  {
    icon: Bug,
    title: "Grouped by what went wrong",
    body: "Pests, temperature control, hygiene, food protection — see the patterns at a glance.",
  },
  {
    icon: Thermometer,
    title: "Straight from the city's record",
    body: "Built on NYC DOHMH inspection data across all five boroughs, refreshed from the source.",
  },
];

export function About() {
  const { ref, inView } = useInView<HTMLDivElement>();
  return (
    <section id="about" className="relative border-t border-hairline">
      <div
        ref={ref}
        className={`mx-auto max-w-6xl px-6 py-24 transition-all duration-700 ${
          inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
        }`}
      >
        <div className="grid gap-12 md:grid-cols-2 md:gap-20">
          <div>
            <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-mint">
              // what it does
            </span>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
              The health inspector's clipboard, made searchable.
            </h2>
          </div>
          <p className="text-lg leading-relaxed text-muted-foreground">
            ScoutEats rolls up hundreds of thousands of DOHMH inspection lines
            into one record per restaurant — violation counts, critical flags,
            and category breakdowns — so you can search, filter, and see who's
            been cited before you decide where to eat.
          </p>
        </div>

        <div className="mt-16 grid gap-4 sm:grid-cols-3">
          {PROPS.map(({ icon: Icon, title, body }, i) => (
            <div
              key={title}
              className="group relative rounded-2xl hairline bg-surface/60 p-6 transition-all hover:-translate-y-0.5 hover:bg-surface"
              style={{ transitionDelay: `${i * 40}ms` }}
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-mint/10 text-mint ring-1 ring-mint/30">
                <Icon className="h-5 w-5" />
              </div>
              <h3 className="mt-5 text-base font-semibold text-foreground">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
