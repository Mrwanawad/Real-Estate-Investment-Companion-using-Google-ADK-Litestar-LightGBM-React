import { useState } from "react";
import { useTranslation } from "react-i18next";

import { BrokerError, LEAD_STATUSES, listLeads, updateLeadStatus, type Lead } from "../api";

const KEY = "broker_api_key";

export default function BrokerPage() {
  const { t, i18n } = useTranslation();
  const [apiKey, setApiKey] = useState(() => sessionStorage.getItem(KEY) ?? "");
  const [status, setStatus] = useState("");
  const [leads, setLeads] = useState<Lead[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fail = (e: unknown) => {
    if (e instanceof BrokerError && e.status === 401) setError(t("broker.unauthorized"));
    else if (e instanceof BrokerError && e.status === 503) setError(t("broker.unavailable"));
    else setError(t("broker.failed"));
  };

  const load = async (nextStatus = status) => {
    sessionStorage.setItem(KEY, apiKey);
    setError(null);
    setLoading(true);
    try {
      setLeads(await listLeads(apiKey, nextStatus));
    } catch (e) {
      setLeads(null);
      fail(e);
    } finally {
      setLoading(false);
    }
  };

  const change = async (lead: Lead, next: string) => {
    setError(null);
    try {
      await updateLeadStatus(apiKey, lead.id, next);
      setLeads((all) => all?.map((l) => (l.id === lead.id ? { ...l, status: next } : l)) ?? null);
    } catch (e) {
      fail(e);
    }
  };

  const fmtDate = (s: string) => {
    const d = new Date(s);
    return Number.isNaN(d.getTime()) ? s : d.toLocaleString(i18n.resolvedLanguage ?? "en");
  };

  return (
    <section className="broker">
      <h2>{t("broker.title")}</h2>
      <form
        className="toolbar"
        onSubmit={(e) => {
          e.preventDefault();
          void load();
        }}
      >
        <label>
          {t("broker.apiKey")}
          <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} autoComplete="off" />
        </label>
        <label>
          {t("broker.filter")}
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              if (apiKey) void load(e.target.value);
            }}
          >
            <option value="">{t("broker.all")}</option>
            {LEAD_STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(`status.${s}`)}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={!apiKey || loading}>
          {t("broker.load")}
        </button>
      </form>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {leads && leads.length === 0 && <p>{t("broker.empty")}</p>}
      {leads && leads.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t("broker.created")}</th>
                <th>{t("broker.name")}</th>
                <th>{t("broker.contact")}</th>
                <th>{t("broker.goal")}</th>
                <th>{t("broker.budget")}</th>
                <th>{t("broker.status")}</th>
                <th>{t("broker.summary")}</th>
              </tr>
            </thead>
            <tbody>
              {leads.map((l) => (
                <tr key={l.id}>
                  <td className="num">{fmtDate(l.created_at)}</td>
                  <td>{l.name ?? "-"}</td>
                  <td className="num">{[l.phone, l.email].filter(Boolean).join(" / ") || "-"}</td>
                  <td>{l.goal ?? "-"}</td>
                  <td className="num">{l.budget_egp != null ? l.budget_egp.toLocaleString(i18n.language) : "-"}</td>
                  <td>
                    <select
                      aria-label={t("broker.status")}
                      value={l.status}
                      onChange={(e) => void change(l, e.target.value)}
                    >
                      {(LEAD_STATUSES.includes(l.status as never) ? LEAD_STATUSES : [l.status, ...LEAD_STATUSES]).map(
                        (s) => (
                          <option key={s} value={s}>
                            {i18n.exists(`status.${s}`) ? t(`status.${s}`) : s}
                          </option>
                        ),
                      )}
                    </select>
                  </td>
                  <td>{l.summary ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
