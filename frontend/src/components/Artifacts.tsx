import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import { API_BASE, type Artifact, type Citation, type FinancingOption, type Projection } from "../api";
import { PlotlyChart } from "./PlotlyChart";

const ACCENT = "#1f4d3a";
const MUTED = "#8a9a91";

function useMoney() {
  const { i18n } = useTranslation();
  return (v: number | string | null | undefined) => {
    const n = Number(v);
    if (v === null || v === undefined || Number.isNaN(n)) return "-";
    return new Intl.NumberFormat(i18n.resolvedLanguage ?? "en", { maximumFractionDigits: 0 }).format(n);
  };
}

function usePct() {
  const { i18n } = useTranslation();
  return (v: number | string) => {
    const n = Number(v);
    if (Number.isNaN(n)) return "-";
    return new Intl.NumberFormat(i18n.resolvedLanguage ?? "en", {
      style: "percent",
      maximumFractionDigits: 1,
    }).format(n);
  };
}

function Financing({ data }: { data: Extract<Artifact, { kind: "financing" }>["data"] }) {
  const { t } = useTranslation();
  const money = useMoney();
  const chart = useMemo(
    () => [
      {
        type: "bar" as const,
        orientation: "h" as const,
        y: data.options.map((o) => o.label),
        x: data.options.map((o) => Number(o.present_value)),
        marker: { color: data.options.map((o) => (o.label === data.cheapest_label ? ACCENT : MUTED)) },
      },
    ],
    [data],
  );
  return (
    <section className="card artifact">
      <h3>{t("artifact.financing", { code: data.unit_code })}</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>{t("financing.option")}</th>
              <th>{t("financing.upfront")}</th>
              <th>{t("financing.monthly")}</th>
              <th>{t("financing.total")}</th>
              <th>{t("financing.pv")}</th>
            </tr>
          </thead>
          <tbody>
            {data.options.map((o: FinancingOption) => (
              <tr key={o.label} className={o.label === data.cheapest_label ? "highlight" : undefined}>
                <th scope="row">
                  {o.label}
                  {o.label === data.cheapest_label && <span className="badge">{t("financing.cheapest")}</span>}
                </th>
                <td className="num">{money(o.upfront)}</td>
                <td className="num">{money(o.avg_monthly_outflow)}</td>
                <td className="num">{money(o.total_nominal)}</td>
                <td className="num">{money(o.present_value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <PlotlyChart
        data={chart}
        layout={{ yaxis: { automargin: true }, margin: { l: 10 } }}
        label={t("financing.chartLabel")}
      />
    </section>
  );
}

function ProjectionView({ data }: { data: Projection }) {
  const { t } = useTranslation();
  const money = useMoney();
  const pct = usePct();
  const chart = useMemo(() => {
    const years = data.value_path.map((p) => p.year);
    return [
      { type: "scatter" as const, x: years, y: data.value_path.map((p) => p.p90), mode: "lines" as const, line: { width: 0, color: ACCENT } },
      {
        type: "scatter" as const,
        x: years,
        y: data.value_path.map((p) => p.p10),
        mode: "lines" as const,
        fill: "tonexty" as const,
        fillcolor: "rgba(31,77,58,0.18)",
        line: { width: 0, color: ACCENT },
      },
      { type: "scatter" as const, x: years, y: data.value_path.map((p) => p.p50), mode: "lines" as const, line: { color: ACCENT, width: 3 } },
    ];
  }, [data]);
  const figures: [string, string][] = [
    [t("projection.valueP50"), money(data.value.p50)],
    [t("projection.valueRange"), `${money(data.value.p10)} - ${money(data.value.p90)}`],
    [t("projection.rent"), money(data.rent.monthly_p50)],
    [t("projection.yield"), pct(data.rent.gross_yield)],
    [t("projection.irr"), `${pct(data.irr.p50)} (${pct(data.irr.p10)} - ${pct(data.irr.p90)})`],
    [t("projection.probLoss"), pct(data.prob_loss)],
    [t("projection.breakEven"), data.break_even_year === null ? t("projection.none") : String(data.break_even_year)],
  ];
  return (
    <section className="card artifact">
      <h3>{t("artifact.projection", { code: data.unit_code, years: data.horizon_years })}</h3>
      <PlotlyChart
        data={chart}
        layout={{ xaxis: { title: { text: t("projection.year") } }, yaxis: { title: { text: "EGP" } } }}
        label={t("projection.chartLabel")}
      />
      <dl className="figures">
        {figures.map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd className="num">{v}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

export function CitationList({ items }: { items: Citation[] }) {
  const { t } = useTranslation();
  return (
    <section className="artifact sources">
      <h3>{t("artifact.sources")}</h3>
      <ol>
        {items.map((c) => (
          <li key={c.doc_id}>
            <strong>{c.title}</strong>
            <span className="snippet"> {c.snippet}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

export function ArtifactView({ artifact }: { artifact: Artifact }) {
  const { t, i18n } = useTranslation();
  const money = useMoney();
  const isAr = (i18n.resolvedLanguage ?? "en").startsWith("ar");
  switch (artifact.kind) {
    case "shortlist":
      return (
        <div className="cards">
          {artifact.data.units.map((u) => (
            <article key={u.code} className="card unit">
              <h3>{u.project_name}</h3>
              <p className="meta">
                {u.area_name} · {u.type} · {t("unit.bedrooms", { count: u.bedrooms })} · {u.bua_m2} {t("unit.m2")}
              </p>
              <p className="price num">{money(u.price_egp)} EGP</p>
              <p className="meta">
                {t("unit.delivery", { year: u.delivery_year })} · {t("unit.tier", { tier: u.developer_tier })} ·{" "}
                {t("unit.score", { score: u.score })}
              </p>
              <ul>
                {u.reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
              <p className="code">{u.code}</p>
            </article>
          ))}
        </div>
      );
    case "financing":
      return <Financing data={artifact.data} />;
    case "projection":
      return <ProjectionView data={artifact.data} />;
    case "risks":
      return (
        <section className="card artifact">
          <h3>{t("artifact.risks")}</h3>
          <ul className="risks">
            {artifact.data.items.map((r) => (
              <li key={r.kind}>
                <span className={`badge level-${r.level}`}>{t(`risk.${r.level}`)}</span>{" "}
                {isAr ? r.explanation_ar : r.explanation_en}
              </li>
            ))}
          </ul>
        </section>
      );
    case "citations":
      return <CitationList items={artifact.data.items} />;
    case "handoff":
      return (
        <p className="note" role="status">
          {t("artifact.handoff", { id: artifact.data.lead_id })}
        </p>
      );
    case "report": {
      const abs = (u: string) => (/^https?:/.test(u) ? u : `${API_BASE}${u}`);
      return (
        <p className="note">
          <a href={abs(artifact.data.url_html)} target="_blank" rel="noreferrer">
            {t("artifact.reportHtml")}
          </a>
          {artifact.data.url_pdf && (
            <>
              {" · "}
              <a href={abs(artifact.data.url_pdf)} target="_blank" rel="noreferrer">
                {t("artifact.reportPdf")}
              </a>
            </>
          )}
        </p>
      );
    }
  }
}
