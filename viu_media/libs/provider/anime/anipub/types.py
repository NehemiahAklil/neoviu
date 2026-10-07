from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, StringConstraints

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AniPubRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: PositiveInt = Field(alias="Id")
    title: Title = Field(alias="Name")
    image: str | None = Field(default=None, alias="Image")


class AniPubInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: PositiveInt = Field(alias="_id")
    title: Title = Field(alias="Name")
    image: str | None = Field(default=None, alias="ImagePath")


class AniPubEpisodeLink(BaseModel):
    link: str | None


class AniPubEpisodeList(AniPubEpisodeLink):
    ep: list[AniPubEpisodeLink] = Field(default_factory=list)


class AniPubDetails(BaseModel):
    local: AniPubEpisodeList
