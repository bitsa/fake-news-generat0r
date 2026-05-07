from pydantic import BaseModel


class ScrapeResponse(BaseModel):
    inserted: int
    fetched: int
    skipped_url_duplicates: int
    skipped_near_duplicates: int
    embedding_calls: int
