from __future__ import annotations
from typing import TYPE_CHECKING
from .models import CollectedElement, CollectedPage
import asyncio
import base64

if TYPE_CHECKING:
    from playwright.async_api import async_playwright, Page, Browser


class BrowserController:
    def __init__(self, viewport: str = "desktop"):
        self.viewport = viewport
        self._browser = None
        self._page = None
        self._context = None
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

    async def _get_page(self, url: str, persist: bool = False):
        if self._page is not None and persist:
            if self._page.url == url:
                return self._page
            await self._page.goto(url, wait_until="networkidle")
            return self._page

        browser = await self._init_browser()
        self._page = await browser.new_page(
            **self._viewport_sizes.get(self.viewport, self._viewport_sizes["desktop"])
        )
        await self._page.goto(url, wait_until="networkidle")
        return self._page

    async def navigate(self, url: str) -> dict:
        page = await self._get_page(url, persist=True)
        return {"status": "ok", "url": page.url, "title": await page.title()}

    async def reload(self) -> dict:
        if self._page is None:
            return {"status": "error", "message": "No page loaded"}
        await self._page.reload(wait_until="networkidle")
        return {"status": "ok", "url": self._page.url}

    async def go_back(self) -> dict:
        if self._page is None:
            return {"status": "error", "message": "No page loaded"}
        await self._page.go_back(wait_until="networkidle")
        return {"status": "ok", "url": self._page.url}

    async def go_forward(self) -> dict:
        if self._page is None:
            return {"status": "error", "message": "No page loaded"}
        await self._page.go_forward(wait_until="networkidle")
        return {"status": "ok", "url": self._page.url}

    async def click(self, selector: str) -> dict:
        if self._page is None:
            return {"status": "error", "message": "No page loaded"}
        try:
            await self._page.click(selector, timeout=5000)
            return {"status": "ok", "action": "click", "selector": selector}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def type(self, selector: str, text: str, clear: bool = True) -> dict:
        if self._page is None:
            return {"status": "error", "message": "No page loaded"}
        try:
            if clear:
                await self._page.fill(selector, text)
            else:
                await self._page.locator(selector).type(text)
            return {
                "status": "ok",
                "action": "type",
                "selector": selector,
                "text": text,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def hover(self, selector: str) -> dict:
        if self._page is None:
            return {"status": "error", "message": "No page loaded"}
        try:
            await self._page.hover(selector)
            return {"status": "ok", "action": "hover", "selector": selector}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def scroll_to(self, selector: str = None, y: int = 0) -> dict:
        if self._page is None:
            return {"status": "error", "message": "No page loaded"}
        try:
            if selector:
                await self._page.locator(selector).scroll_into_view_if_needed()
            else:
                await self._page.evaluate(f"window.scrollTo(0, {y})")
            return {"status": "ok", "action": "scroll", "selector": selector, "y": y}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def wait_for_selector(self, selector: str, timeout: int = 5000) -> dict:
        if self._page is None:
            return {"status": "error", "message": "No page loaded"}
        try:
            await self._page.wait_for_selector(selector, timeout=timeout)
            return {"status": "ok", "selector": selector}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def wait_for_navigation(self, timeout: int = 5000) -> dict:
        if self._page is None:
            return {"status": "error", "message": "No page loaded"}
        try:
            await self._page.wait_for_load_state("networkidle", timeout=timeout)
            return {"status": "ok", "url": self._page.url}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def screenshot(self, full_page: bool = False, path: str = None) -> str:
        if self._page is None:
            return ""
        if path:
            await self._page.screenshot(full_page=full_page, path=path)
            return path
        screenshot = await self._page.screenshot(full_page=full_page)
        return base64.b64encode(screenshot).decode("utf-8")

    async def get_url(self) -> str:
        return self._page.url if self._page else ""

    async def close(self):
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._page = None


class Collector(BrowserController):
    async def collect(self, url: str) -> CollectedPage:
        page = await self._get_page(url)
        elements = await self._extract_elements(page)
        screenshot_b64 = await self.screenshot(full_page=True)

        return CollectedPage(
            url=url,
            viewport=self.viewport,
            full_screenshot=screenshot_b64,
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


async def collect_page(url: str, viewport: str = "desktop") -> CollectedPage:
    collector = Collector(viewport=viewport)
    try:
        return await collector.collect(url)
    finally:
        await collector.close()


async def create_controller(viewport: str = "desktop") -> BrowserController:
    return BrowserController(viewport=viewport)
