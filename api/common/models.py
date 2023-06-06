from api.util.util import get_current_time_gb


class BaseModel:
    def __init__(self):
        current_time = get_current_time_gb()
        self.created = current_time
        self.last_modified = current_time
