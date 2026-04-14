import re
from collections import defaultdict
from .models import DesignToken, ComponentDef, AnalysisResult


ELEMENT_ROLE_PATTERNS = {
    "button": r"^(button|a\.btn|a\.button|input\[type=submit\])$",
    "input": r"^(input|textarea|select)$",
    "heading": r"^(h[1-6])$",
    "paragraph": r"^(p|span|div)$",
    "link": r"^(a)$",
    "image": r"^(img|figure|picture)$",
    "card": r"^(div\.card|article|section)$",
    "nav": r"^(nav|header|footer|aside)$",
    "list": r"^(ul|ol|li)$",
    "form": r"^(form)$",
    "table": r"^(table|thead|tbody|tr|th|td)$",
}


def _classify_element(tag: str, text: str | None, styles: dict) -> str:
    tag_lower = tag.lower()
    if text and len(text) < 50:
        text_lower = text.lower()
        if any(
            kw in text_lower
            for kw in ["submit", "send", "click", "sign in", "login", "register"]
        ):
            return "button"
        if any(kw in text_lower for kw in ["search", "find", "query"]):
            return "input"

    for role, pattern in ELEMENT_ROLE_PATTERNS.items():
        if re.match(pattern, tag_lower):
            return role

    display = styles.get("display", "")
    if display in ["flex", "grid"]:
        return "container"

    return "unknown"


def _normalize_color(color: str) -> str | None:
    if not color or color in ["transparent", "rgba(0, 0, 0, 0)", "inherit"]:
        return None

    color = color.strip().lower()
    if color.startswith("#"):
        return color
    if color.startswith("rgb"):
        return color

    return color


def _extract_colors(elements: list[dict]) -> dict[str, list[str]]:
    colors = defaultdict(list)

    for el in elements:
        styles = el.get("computedStyles", {})

        bg = _normalize_color(styles.get("backgroundColor"))
        if bg and bg not in colors["background"]:
            colors["background"].append(bg)

        fg = _normalize_color(styles.get("color"))
        if fg and fg not in colors["text"]:
            colors["text"].append(fg)

        border = _normalize_color(styles.get("border") or styles.get("borderTopColor"))
        if border and border not in colors["border"]:
            colors["border"].append(border)

    for category in colors:
        colors[category] = _dedupe_colors(colors[category])

    return dict(colors)


def _dedupe_colors(colors: list[str]) -> list[str]:
    hex_to_name = {}
    unique = []

    for c in colors:
        if c.startswith("#"):
            hex_to_name[c.upper()] = c
        else:
            unique.append(c)

    unique.extend(hex_to_name.values())
    return unique[:20]


def _extract_typography(elements: list[dict]) -> dict[str, list[str]]:
    fonts = defaultdict(list)

    for el in elements:
        styles = el.get("computedStyles", {})
        font_family = styles.get("fontFamily", "")
        font_size = styles.get("fontSize", "")
        font_weight = styles.get("fontWeight", "")

        if font_family:
            fonts["families"].append(font_family)
        if font_size:
            fonts["sizes"].append(font_size)
        if font_weight:
            fonts["weights"].append(font_weight)

    return {
        "families": list(set(fonts["families"]))[:10],
        "sizes": list(set(fonts["sizes"]))[:10],
        "weights": list(set(fonts["weights"]))[:10],
    }


def _extract_spacing(elements: list[dict]) -> dict[str, list[str]]:
    spacing = defaultdict(list)

    for el in elements:
        styles = el.get("computedStyles", {})

        padding = styles.get("padding", "")
        if padding and padding != "0px":
            spacing["padding"].append(padding)

        margin = styles.get("margin", "")
        if margin and margin != "0px":
            spacing["margin"].append(margin)

    return {
        "padding": list(set(spacing["padding"]))[:10],
        "margin": list(set(spacing["margin"]))[:10],
    }


def _extract_tokens(elements: list[dict]) -> list[DesignToken]:
    tokens = []

    colors = _extract_colors(elements)
    for category, color_list in colors.items():
        for color in color_list:
            tokens.append(
                DesignToken(
                    name=f"color-{category}",
                    value=color,
                    category="color",
                )
            )

    typography = _extract_typography(elements)
    for font in typography.get("families", []):
        tokens.append(
            DesignToken(
                name=f"font-{font[:20]}",
                value=font,
                category="typography",
            )
        )

    spacing = _extract_spacing(elements)
    for pad in spacing.get("padding", [])[:5]:
        tokens.append(
            DesignToken(
                name=f"spacing-{pad}",
                value=pad,
                category="spacing",
            )
        )

    return tokens


def _extract_components(elements: list[dict]) -> list[ComponentDef]:
    component_groups = defaultdict(list)

    for el in elements:
        styles = el.get("computedStyles", {})
        tag = el.get("tag", "")
        text = el.get("textContent", "")

        role = _classify_element(tag, text, styles)
        key = f"{role}"

        component_groups[key].append(el)

    components = []
    for role, els in component_groups.items():
        if len(els) < 2:
            continue

        variants = {}
        for el in els[:5]:
            styles = el.get("computedStyles", {})
            bg = styles.get("backgroundColor", "default")
            variants[f"variant_{len(variants) + 1}"] = {"backgroundColor": bg}

        components.append(
            ComponentDef(
                name=role,
                variants=variants,
                source_elements=[e.get("xpath", "") for e in els[:5]],
            )
        )

    return components


async def analyze_page(collected_data: dict) -> AnalysisResult:
    elements = collected_data.get("elements", [])

    elements_dicts = [
        {
            "tag": e.xpath.split("/")[-1].split("[")[0] if e.xpath else "",
            "xpath": e.xpath,
            "textContent": e.text_content,
            "computedStyles": e.computed_styles,
        }
        for e in elements
    ]

    tokens = _extract_tokens(elements_dicts)
    components = _extract_components(elements_dicts)
    color_palette = _extract_colors(elements_dicts)
    typography_scale = _extract_typography(elements_dicts)
    spacing_scale = _extract_spacing(elements_dicts)

    return AnalysisResult(
        tokens=tokens,
        components=components,
        color_palette=color_palette,
        typography_scale=typography_scale,
        spacing_scale=spacing_scale,
    )
