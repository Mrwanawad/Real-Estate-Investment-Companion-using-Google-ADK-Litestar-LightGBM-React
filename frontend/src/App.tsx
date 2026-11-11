import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import BrokerPage from "./components/BrokerPage";
import ChatPage from "./components/ChatPage";
import { directionFor } from "./i18n";

export default function App() {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage ?? "en";
  const [hash, setHash] = useState(window.location.hash);

  useEffect(() => {
    document.documentElement.dir = directionFor(language);
    document.documentElement.lang = language;
  }, [language]);

  useEffect(() => {
    const onHash = () => setHash(window.location.hash);
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const toggle = () => void i18n.changeLanguage(language === "en" ? "ar-EG" : "en");
  const broker = hash === "#/broker";

  return (
    <main>
      <div role="status" className="banner">
        {t("banner.synthetic")}
      </div>
      <header className="top">
        <h1>{t("app.title")}</h1>
        <nav>
          <a href={broker ? "#/" : "#/broker"}>{broker ? t("nav.chat") : t("nav.broker")}</a>
          <button type="button" className="secondary" onClick={toggle}>
            {t("language.toggle")}
          </button>
        </nav>
      </header>
      {broker ? <BrokerPage /> : <ChatPage key={language} />}
    </main>
  );
}
