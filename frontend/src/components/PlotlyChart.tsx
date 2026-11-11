import { useEffect, useRef } from "react";
import type { Data, Layout } from "plotly.js-dist-min";

interface Props {
  data: Data[];
  layout?: Partial<Layout>;
  label: string;
}

const BASE_LAYOUT: Partial<Layout> = {
  margin: { t: 16, r: 16, b: 48, l: 64 },
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  font: { family: "Times New Roman, serif", color: "#1a1a1a", size: 13 },
  height: 280,
  showlegend: false,
};

export function PlotlyChart({ data, layout, label }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let cancelled = false;
    import("plotly.js-dist-min")
      .then((mod) => {
        if (cancelled) return;
        return mod.default.react(el, data, { ...BASE_LAYOUT, ...layout }, { responsive: true, displayModeBar: false });
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [data, layout]);
  return <div ref={ref} className="chart" role="img" aria-label={label} />;
}
