import { useTranslation } from "react-i18next";

export default function PrivacyPage() {
  const { t } = useTranslation();
  const paragraphs = t("legal.privacyBody", { returnObjects: true }) as string[];
  return (
    <section className="privacy">
      <h2>{t("legal.privacyTitle")}</h2>
      {paragraphs.map((p, i) => (
        <p key={i}>{p}</p>
      ))}
    </section>
  );
}
