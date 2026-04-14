from __future__ import annotations
from typing import TYPE_CHECKING
from .models import CollectedElement, CollectedPage
import asyncio

if TYPE_CHECKING:
    from playwright.async_api import async_playwright, Page, Browser


class Collector:
    def __init__(self, viewport: str = "desktop"):
        self.viewport = viewport
        self._browser = None
        self._page = None
        self._viewport_sizes = {
            "desktop": {"width": 1440, "height": 900},
            "tablet": {"width": 768, "height": 1024},
            "mobile": {"width": 375, "height": 667},
        }

    async def _init_browser(self):
        if self._browser is None:
            from playwright.async_api import async_playwright

            pw = await async_playwright().start()
            self._browser = await pw.chromium.launch(headless=True)
        return self._browser

    async def _init_page(self, url: str):
        from playwright.async_api import Page

        browser = await self._init_browser()
        self._page = await browser.new_page(
            **self._viewport_sizes.get(self.viewport, self._viewport_sizes["desktop"])
        )
        await self._page.goto(url, wait_until="networkidle")
        return self._page

    async def collect(self, url: str) -> CollectedPage:
        page = await self._init_page(url)
        elements = await self._extract_elements(page)
        screenshot = await page.screenshot(full_page=True)

        full_screenshot_b64 = (
            screenshot.encode("base64").decode("utf-8") if screenshot else None
        )

        return CollectedPage(
            url=url,
            viewport=self.viewport,
            full_screenshot=full_screenshot_b64,
            elements=elements,
            assets=[],
        )

    async def _extract_elements(self, page) -> list[CollectedElement]:
        elements_data = await page.evaluate("""() => {
            const elements = document.querySelectorAll('*');
            const results = [];
            const seen = new Set();
            
            function getXPath(el) {
                if (el.id) return `//*[@id="${el.id}"]`;
                let path = [];
                while (el && el.nodeType === 1) {
                    let pe = el;
                    let idx = 1;
                    while (pe && pe.previousElementSibling) {
                        if (pe.previousElementSibling.tagName === el.tagName) idx++;
                        pe = pe.previousElementSibling;
                    }
                    path.unshift(`${el.tagName.toLowerCase()}[${idx}]`);
                    el = el.parentNode;
                }
                return '/' + path.join('/');
            }
            
            for (const el of elements) {
                if (el.children.length > 1) continue;
                
                const rect = el.getBoundingClientRect();
                if (rect.width < 5 || rect.height < 5) continue;
                if (rect.width > 3000 || rect.height > 3000) continue;
                
                const computed = window.getComputedStyle(el);
                const key = `${rect.x}-${rect.y}-${rect.width}-${rect.height}-${el.tagName}`;
                if (seen.has(key)) continue;
                seen.add(key);
                
                results.push({
                    xpath: getXPath(el),
                    tag: el.tagName.toLowerCase(),
                    computedStyles: {
                        fontFamily: computed.fontFamily,
                        fontSize: computed.fontSize,
                        fontWeight: computed.fontWeight,
                        color: computed.color,
                        backgroundColor: computed.backgroundColor,
                        display: computed.display,
                        position: computed.position,
                        padding: computed.padding,
                        margin: computed.margin,
                        borderRadius: computed.borderRadius,
                        boxShadow: computed.boxShadow,
                    },
                    boundingBox: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                    textContent: el.textContent?.trim().slice(0, 100) || null,
                });
            }
            return results;
        }""")

        return [CollectedElement(**e) for e in elements_data]

    async def close(self):
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._page = None


async def collect_page(url: str, viewport: str = "desktop") -> CollectedPage:
    collector = Collector(viewport=viewport)
    try:
        return await collector.collect(url)
    finally:
        await collector.close()
