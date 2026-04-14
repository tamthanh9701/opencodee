from pydantic import BaseModel


class FigmaCreateRequest(BaseModel):
    project_name: str
    tokens: dict
    components: list[dict]


class FigmaCreateResult(BaseModel):
    file_key: str
    file_url: str
    styles_created: int = 0
    components_created: int = 0