from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class AvitoListing(BaseModel):
    avito_id: str
    title: str
    price: Optional[int]
    url: str
    location: Optional[str]
    seller_type: Optional[str]    # Частное лицо/Компания
    image_url: List[str] = []
    parsed_at: datetime

    