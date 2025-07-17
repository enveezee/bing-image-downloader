from dataclasses import dataclass, field
from typing import List, Optional
import datetime

@dataclass(repr=False)
class ImageData:
    """Holds all the data for a single image."""
    title: Optional[str] = None
    size: Optional[str] = None
    file_type: Optional[str] = None
    date: Optional[str] = None
    ago: Optional[str] = None
    site_source: Optional[str] = None
    image_source_url: Optional[str] = None
    data_idx: Optional[str] = None
    thumbnail: Optional[bytes] = None
    related_images: List['ImageData'] = field(default_factory=list)
    downloaded_path: Optional[str] = None
    parsed_date: Optional[datetime.date] = None
    parsed_age: Optional[int] = None

    def __repr__(self):
        return (
            f"ImageData(title='{self.title}', size='{self.size}', "
            f"file_type='{self.file_type}', date='{self.date}', ago='{self.ago}', "
            f"site_source='{self.site_source}', image_source_url='{self.image_source_url}', "
            f"data_idx='{self.data_idx}', downloaded_path='{self.downloaded_path}', "
            f"parsed_date='{self.parsed_date}', parsed_age='{self.parsed_age}')"
        )