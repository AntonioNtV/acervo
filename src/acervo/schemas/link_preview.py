from pydantic import BaseModel, Field


class LinkPreview(BaseModel):
    """What a site says about itself, for the card of a link; only `url` and `domain` when it did not answer."""

    url: str = Field(description="The URL asked for.")
    domain: str = Field(description="Its host.")
    title: str | None = Field(default=None, description="The page's og:title, else its <title>.")
    description: str | None = Field(default=None, description="The page's og:description, else its meta description.")
    image: str | None = Field(default=None, description="The page's og:image as an absolute http(s) URL, on the site.")
