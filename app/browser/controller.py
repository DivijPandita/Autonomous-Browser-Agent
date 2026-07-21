"""
BrowserController wraps Playwright and exposes a small, agent-friendly API.

Key idea (used by most real browser agents - WebVoyager, browser-use, etc.):
Instead of asking the LLM to write CSS selectors blindly (which it's bad at,
since it can't see the live DOM structure), we scan the page ourselves for
interactive elements, number them, and hand the LLM a short numbered list like:

    [3] <button> "Search"
    [4] <input placeholder="Enter city"> ""
    [7] <a> "Next page"

The LLM then just says "click element 3" or "type 'Mumbai' into element 4".
We map that index back to the real element and act on it. This is far more
reliable than raw selector generation.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from app.core.config import settings

INTERACTIVE_ELEMENTS_JS = """
() => {
    const selector = 'a, button, input, textarea, select, [role="button"], [contenteditable="true"]';
    const elements = Array.from(document.querySelectorAll(selector));
    const results = [];
    let index = 0;

    for (const el of elements) {
        const rect = el.getBoundingClientRect();
        const visible = rect.width > 0 && rect.height > 0 &&
            window.getComputedStyle(el).visibility !== 'hidden' &&
            window.getComputedStyle(el).display !== 'none';
        if (!visible) continue;

        el.setAttribute('data-agent-id', String(index));

        const text = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '')
            .trim().slice(0, 120);

        results.push({
            index: index,
            tag: el.tagName.toLowerCase(),
            type: el.getAttribute('type') || '',
            text: text,
        });
        index += 1;
    }
    return results;
}
"""


@dataclass
class InteractiveElement:
    index: int
    tag: str
    type: str
    text: str

    def to_prompt_line(self) -> str:
        type_str = f' type="{self.type}"' if self.type else ""
        return f'[{self.index}] <{self.tag}{type_str}> "{self.text}"'


class BrowserController:
    def __init__(self) -> None:
        self._playwright = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        os.makedirs(settings.screenshot_dir, exist_ok=True)

    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(headless=settings.headless)
        self.context = await self.browser.new_context(viewport={"width": 1366, "height": 900})
        self.page = await self.context.new_page()
        self.page.set_default_timeout(settings.nav_timeout_ms)

    async def close(self) -> None:
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def goto(self, url: str) -> None:
        await self.page.goto(url, wait_until="domcontentloaded")

    async def get_interactive_elements(self) -> list[InteractiveElement]:
        raw = await self.page.evaluate(INTERACTIVE_ELEMENTS_JS)
        return [InteractiveElement(**item) for item in raw]

    async def click(self, agent_id: int) -> None:
        locator = self.page.locator(f'[data-agent-id="{agent_id}"]')
        await locator.click(timeout=settings.nav_timeout_ms)

    async def type_text(self, agent_id: int, text: str, clear_first: bool = True) -> None:
        locator = self.page.locator(f'[data-agent-id="{agent_id}"]')
        if clear_first:
            await locator.fill("")
        await locator.fill(text)

    async def press_key(self, key: str) -> None:
        await self.page.keyboard.press(key)

    async def scroll(self, direction: str = "down") -> None:
        delta = 800 if direction == "down" else -800
        await self.page.mouse.wheel(0, delta)

    async def extract_text(self, agent_id: int | None = None) -> str:
        if agent_id is not None:
            locator = self.page.locator(f'[data-agent-id="{agent_id}"]')
            return (await locator.inner_text()).strip()
        return (await self.page.inner_text("body")).strip()

    async def screenshot(self) -> str:
        path = os.path.join(settings.screenshot_dir, f"{int(time.time() * 1000)}.png")
        await self.page.screenshot(path=path)
        return path

    @property
    def current_url(self) -> str:
        return self.page.url if self.page else ""