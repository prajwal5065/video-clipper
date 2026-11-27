"""Request bodies for the API."""
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from clipper.captions import STYLES
from clipper.download import is_url

Crop = Literal["face", "center", "fit", "fit-black"]
Quality = Literal["draft", "standard", "high", "max"]
Whisper = Literal["tiny", "base", "small", "medium", "large-v3"]


class JobSpec(BaseModel):
    source_type: Literal["link", "path"]
    source: str = Field(min_length=1)
    clips: int = Field(5, ge=1, le=20)
    min_len: int = Field(20, ge=5, le=120)
    max_len: int = Field(60, ge=10, le=180)
    whisper: Whisper = "small"
    device: Literal["auto", "cpu", "cuda"] = "auto"
    compute_type: Literal["int8", "float16"] = "int8"
    crop: Crop = "face"
    quality: Quality = "standard"
    captions: bool = True
    style: str = "classic"
    model: Optional[str] = None

    @model_validator(mode="after")
    def _check(self):
        if self.min_len > self.max_len:
            raise ValueError("min_len must not be longer than max_len")
        if self.style not in STYLES:
            raise ValueError(f"style must be one of {list(STYLES)}")
        self.source = self.source.strip().strip('"')
        if self.source_type == "link" and not is_url(self.source):
            raise ValueError("A link must start with http:// or https://")
        return self


class EditSpec(BaseModel):
    mode: Literal["preview", "final"]
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    crop: Optional[Crop] = None
    style: Optional[str] = None
    captions: Optional[bool] = None
    text: Optional[str] = None  # corrected caption text (same number of words)

    @model_validator(mode="after")
    def _check(self):
        if self.style is not None and self.style not in STYLES:
            raise ValueError(f"style must be one of {list(STYLES)}")
        return self


class MetaBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field("", max_length=6000)
    hashtags: list[str] = []
    tags: list[str] = []


class GenerateMetaBody(BaseModel):
    model: Optional[str] = None
    context: Optional[str] = Field(None, max_length=1000)  # e.g. "Reacting to <creator>'s new video"


class UploadBody(BaseModel):
    account: Optional[str] = None
    privacy: Optional[Literal["private", "unlisted", "public"]] = None
    made_for_kids: Optional[bool] = None
    publish_at: Optional[str] = None  # ISO 8601 with time zone, e.g. 2026-11-25T18:00:00+05:30
    model: Optional[str] = None
