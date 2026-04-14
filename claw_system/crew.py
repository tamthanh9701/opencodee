from shared.config import settings

_crewai = None


def _get_crewai():
    global _crewai
    if _crewai is None:
        from crewai import Agent, Task, Crew, Process
        _crewai = type("CrewAIMod", (), {"Agent": Agent, "Task": Task, "Crew": Crew, "Process": Process})
    return _crewai


def _get_llm() -> str:
    return settings.litellm_model


def _make_collector_agent():
    crewai = _get_crewai()
    return crewai.Agent(
        role="UI Collector",
        goal="Scrape web pages and extract all UI elements with their computed styles, screenshots, and assets",
        backstory=(
            "You are an expert web scraper specializing in design artifact extraction. "
            "You use headless browsers to capture every visual detail of a web page, "
            "including computed CSS styles, element positions, screenshots, and downloadable assets. "
            "Your output is a structured representation of the entire page's visual properties."
        ),
        tools=[],
        llm=_get_llm(),
        verbose=True,
    )


def _make_analyst_agent():
    crewai = _get_crewai()
    return crewai.Agent(
        role="UI Analyst",
        goal="Analyze collected UI data and produce design tokens with component definitions",
        backstory=(
            "You are a senior design systems engineer who sees patterns in visual chaos. "
            "Given raw UI element data, you classify elements into roles (button, input, card, etc.), "
            "extract design tokens (colors, typography, spacing, shadows), "
            "group element variants, and assign confidence scores. "
            "Your output is a complete design specification ready for Figma."
        ),
        tools=[],
        llm=_get_llm(),
        verbose=True,
    )


def _make_fig_agent():
    crewai = _get_crewai()
    return crewai.Agent(
        role="Figma Design System Builder",
        goal="Transform design tokens and component definitions into a structured Figma Design System",
        backstory=(
            "You are a Figma API expert who turns design tokens into living design systems. "
            "You create color styles, text styles, effect styles, and component variants "
            "programmatically through the Figma REST API. Your output is a fully structured "
            "Figma file with a complete, documented design system."
        ),
        tools=[],
        llm=_get_llm(),
        verbose=True,
    )


def build_collect_task(url: str):
    crewai = _get_crewai()
    return crewai.Task(
        description=(
            f"Scrape the web page at {url} and extract all UI elements. "
            "For each element, capture: tag name, computed CSS styles (font, color, spacing, "
            "border, shadow), bounding box position, text content, and a cropped screenshot. "
            "Also download all images, SVGs, and icon assets. "
            "Return a CollectedPage object with all this data."
        ),
        agent=_make_collector_agent(),
        expected_output="CollectedPage object with url, viewport, full_screenshot, elements list, and assets list",
    )


def build_analyze_task():
    crewai = _get_crewai()
    return crewai.Task(
        description=(
            "Analyze the collected UI data from the previous step. "
            "Classify each element into a role (button, input, card, nav, typography, etc.). "
            "Extract design tokens: color palette, typography scale, spacing scale, border radii, shadows. "
            "Group elements into component variants (e.g., button/primary, button/secondary). "
            "Assign confidence scores to each token. "
            "Return an AnalysisResult object with all tokens and component definitions."
        ),
        agent=_make_analyst_agent(),
        expected_output="AnalysisResult object with tokens, components, color_palette, typography_scale, and spacing_scale",
    )


def build_fig_task():
    crewai = _get_crewai()
    return crewai.Task(
        description=(
            "Create a Figma Design System from the analysis results. "
            "Using the Figma API, create: 1) Color styles from the color palette, "
            "2) Text styles from the typography scale, 3) Effect styles from shadows, "
            "4) Component frames with auto-layout and variants for each component definition. "
            "Return the Figma file URL and key of the created design system."
        ),
        agent=_make_fig_agent(),
        expected_output="Figma file URL with the complete design system",
    )


class ClawCrew:
    def __init__(self) -> None:
        self._agents = None

    @property
    def agents(self):
        if self._agents is None:
            self._agents = [_make_collector_agent(), _make_analyst_agent(), _make_fig_agent()]
        return self._agents

    def create_crew(self, url: str):
        crewai = _get_crewai()
        collect_task = build_collect_task(url)
        analyze_task = build_analyze_task()
        fig_task = build_fig_task()

        return crewai.Crew(
            agents=self.agents,
            tasks=[collect_task, analyze_task, fig_task],
            process=crewai.Process.sequential,
            verbose=True,
        )