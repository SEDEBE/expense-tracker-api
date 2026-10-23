import json

from rest_framework.renderers import BaseRenderer


class CSVRenderer(BaseRenderer):
    """Lets a client ask for `Accept: text/csv`. The CSV itself is built by the view; this only
    renders error responses (401, 400...), which stay JSON text."""

    media_type = "text/csv"
    format = "csv"
    charset = "utf-8"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if isinstance(data, str | bytes):
            return data
        return json.dumps(data)
