"""Demo scene for docs/demo.gif. Needs the stack running (fake provider, no key needed):
  python scripts/dev_stack.py --provider fake --port 8710
  cd frontend && VITE_API_URL=http://localhost:8710 npx vite --port 8711   (API CORS_ORIGINS must allow it)
Record:  python docs/demo/scene.py
Compose: python ~/.claude/skills/demo-gif/scripts/compose.py docs/demo/build --out docs/demo.gif
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/skills/demo-gif/scripts"))
from pathlib import Path

from director import Director, run

URL = os.environ.get("DEMO_URL", "http://localhost:8711")
IDLE = "() => !document.querySelector('form.composer button.secondary').disabled"


async def turn_done(p):
    await asyncio.sleep(0.8)
    await p.wait_for_function(IDLE, timeout=120_000)


async def scene(d: Director):
    p = d.page
    chat = p.get_by_label("Ask about units, financing or returns")
    await d.goto(URL, settle=1.5)
    await chat.wait_for()

    await d.caption("Describe your goal", step=1)
    await d.click(p.locator("button.chip").first)

    await d.fast(turn_done(p), label="Running the tools")
    await d.caption("Compare cash, installments, mortgage", step=2)
    table = p.locator("table").first
    await d.focus(table, zoom=1.35)
    await d.spotlight(p.locator("tr.highlight").first)
    await d.hold(1.6)
    await d.clear_spotlight()
    await d.unfocus()

    await d.caption("Ask about company policy", step=3)
    await d.type(chat, "What is the refund policy?")
    await d.press("Enter")
    await d.fast(turn_done(p), label="Searching documents")
    await d.hold(1.8)

    await d.caption("Hand off to a broker", step=4)
    await d.click(p.locator("form.composer button.secondary"))
    await d.fast(turn_done(p), label="Creating lead")
    await d.scroll(600, dur=0.6)
    await d.hold(2.2)


run(
    scene,
    out=str(Path(__file__).with_name("build")),
    title="Real Estate Investment Companion",
    subtitle="From a budget and a goal to a decision pack, in English or Arabic",
    url_label="localhost",
)
