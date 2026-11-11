import type { ReactNode } from "react";

function inline(text: string, keyPrefix: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") && part.length > 4 ? (
      <strong key={`${keyPrefix}${i}`}>{part.slice(2, -2)}</strong>
    ) : (
      part
    ),
  );
}

/** Tiny safe markdown: paragraphs, **bold**, "- " bullet lists. Output is React nodes only. */
export function renderMarkdown(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  let para: string[] = [];
  let bullets: string[] = [];
  const flushPara = () => {
    if (para.length) out.push(<p key={`p${out.length}`}>{inline(para.join(" "), `p${out.length}`)}</p>);
    para = [];
  };
  const flushList = () => {
    if (bullets.length)
      out.push(
        <ul key={`u${out.length}`}>
          {bullets.map((b, i) => (
            <li key={i}>{inline(b, `l${out.length}-${i}`)}</li>
          ))}
        </ul>,
      );
    bullets = [];
  };
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    const m = /^[-*]\s+(.*)$/.exec(line);
    if (m) {
      flushPara();
      bullets.push(m[1]);
    } else if (line === "") {
      flushPara();
      flushList();
    } else {
      flushList();
      para.push(line);
    }
  }
  flushPara();
  flushList();
  return out;
}

export function Markdown({ text }: { text: string }) {
  return <div className="md">{renderMarkdown(text)}</div>;
}
