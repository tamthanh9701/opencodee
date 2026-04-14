from pydantic import BaseModel, Field


class CollectedElement(BaseModel):
    xpath: str
    tag: str
    computed_styles: dict
    bounding_box: dict
    text_content: str | None = None
    screenshot_clip: str | None = None


class CollectedPage(BaseModel):
    url: str
    viewport: str = "desktop"
    full_screenshot: str | None = None
    elements: list[CollectedElement] = Field(default_factory=list)
    assets: list[str] = Field(default_factory=list)