from pydantic import BaseModel, Field


class DesignToken(BaseModel):
    name: str
    value: str
    category: str
    source_elements: list[str] = Field(default_factory=list)
    confidence: float = 1.0


class ComponentDef(BaseModel):
    name: str
    tokens: list[str] = Field(default_factory=list)
    variants: dict = Field(default_factory=dict)
    source_elements: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    tokens: list[DesignToken] = Field(default_factory=list)
    components: list[ComponentDef] = Field(default_factory=list)
    color_palette: dict[str, list[str]] = Field(default_factory=dict)
    typography_scale: dict[str, dict] = Field(default_factory=dict)
    spacing_scale: dict[str, str] = Field(default_factory=dict)