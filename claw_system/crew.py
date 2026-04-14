from __future__ import annotations
from typing import TYPE_CHECKING
from shared.config import settings

if TYPE_CHECKING:
    from crewai import Agent, Task, Crew, Process


def get_llm():
    return settings.litellm_model


def create_collector_agent():
    return Agent(
        role="UI Collector",
        goal="Scrape web pages and extract all UI elements with their computed styles, screenshots, and assets",
        backstory=(
            "You are an expert web scraper specializing in design artifact extraction. "
            "You use headless browsers to capture every visual detail of a web page, "
            "including computed CSS styles, element positions, screenshots, and downloadable assets. "
            "Your output is a structured representation of the entire page's visual properties."
        ),
        tools=[],
        llm=get_llm(),
        verbose=True,
    )


def create_analyst_agent():
    return Agent(
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
        llm=get_llm(),
        verbose=True,
    )


def create_fig_agent():
    return Agent(
        role="Figma Design System Builder",
        goal="Transform design tokens and component definitions into a structured Figma Design System",
        backstory=(
            "You are a Figma API expert who turns design tokens into living design systems. "
            "You create color styles, text styles, effect styles, and component variants "
            "programmatically through the Figma REST API. Your output is a fully structured "
            "Figma file with a complete, documented design system."
        ),
        tools=[],
        llm=get_llm(),
        verbose=True,
    )


def build_collect_task(url: str, agent: Agent):
    return Task(
        description=(
            f"Scrape the web page at {url} and extract all UI elements. "
            "For each element, capture: tag name, computed CSS styles (font, color, spacing, "
            "border, shadow), bounding box position, text content, and a cropped screenshot. "
            "Also download all images, SVGs, and icon assets. "
            "Return a CollectedPage object with all this data."
        ),
        agent=agent,
        expected_output="CollectedPage object with url, viewport, full_screenshot, elements list, and assets list",
    )


def build_analyze_task(agent: Agent):
    return Task(
        description=(
            "Analyze the collected UI data from the previous step. "
            "Classify each element into a role (button, input, card, nav, typography, etc.). "
            "Extract design tokens: color palette, typography scale, spacing scale, border radii, shadows. "
            "Group elements into component variants (e.g., button/primary, button/secondary). "
            "Assign confidence scores to each token. "
            "Return an AnalysisResult object with all tokens and component definitions."
        ),
        agent=agent,
        expected_output="AnalysisResult object with tokens, components, color_palette, typography_scale, and spacing_scale",
    )


def build_fig_task(agent: Agent):
    return Task(
        description=(
            "Create a Figma Design System from the analysis results. "
            "Using the Figma API, create: 1) Color styles from the color palette, "
            "2) Text styles from the typography scale, 3) Effect styles from shadows, "
            "4) Component frames with auto-layout and variants for each component definition. "
            "Return the Figma file URL and key of the created design system."
        ),
        agent=agent,
        expected_output="Figma file URL with the complete design system",
    )


class ClawCrew:
    def __init__(self) -> None:
        self._collector_agent = None
        self._analyst_agent = None
        self._fig_agent = None
        self._crew = None

    @property
    def collector_agent(self):
        if self._collector_agent is None:
            self._collector_agent = create_collector_agent()
        return self._collector_agent

    @property
    def analyst_agent(self):
        if self._analyst_agent is None:
            self._analyst_agent = create_analyst_agent()
        return self._analyst_agent

    @property
    def fig_agent(self):
        if self._fig_agent is None:
            self._fig_agent = create_fig_agent()
        return self._fig_agent

    def create_crew(self, url: str):
        collect_task = build_collect_task(url, self.collector_agent)
        analyze_task = build_analyze_task(self.analyst_agent)
        fig_task = build_fig_task(self.fig_agent)

        self._crew = Crew(
            agents=[self.collector_agent, self.analyst_agent, self.fig_agent],
            tasks=[collect_task, analyze_task, fig_task],
            process=Process.sequential,
            verbose=True,
        )
        return self._crew

    def kickoff(self, url: str):
        if self._crew is None:
            self.create_crew(url)
        return self._crew.kickoff()


def run_pipeline(url: str):
    crew = ClawCrew()
    return crew.kickoff(url)
