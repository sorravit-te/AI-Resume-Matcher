"""Typed representations of text extracted from a resume PDF."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ResumePage(BaseModel):
    """Text extracted from one PDF page, using one-based page numbering."""

    model_config = ConfigDict(frozen=True)

    page_number: int = Field(ge=1)
    text: str
    character_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_character_count(self) -> "ResumePage":
        if self.character_count != len(self.text):
            raise ValueError("character_count must equal the length of text")
        return self


class ResumeDocument(BaseModel):
    """A complete, page-preserving text extraction from a resume PDF."""

    model_config = ConfigDict(frozen=True)

    filename: str | None = None
    page_count: int = Field(ge=1)
    pages: list[ResumePage] = Field(min_length=1)
    full_text: str
    character_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_document_structure(self) -> "ResumeDocument":
        if self.page_count != len(self.pages):
            raise ValueError("page_count must equal the number of pages")
        if [page.page_number for page in self.pages] != list(range(1, self.page_count + 1)):
            raise ValueError("pages must use consecutive one-based page numbers")
        if self.character_count != len(self.full_text):
            raise ValueError("character_count must equal the length of full_text")
        return self
