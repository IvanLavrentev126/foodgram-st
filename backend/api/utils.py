import base64
import re
import uuid

from django.core.files.base import ContentFile
from rest_framework import serializers

BASE64_RE = re.compile(r'^[A-Za-z0-9+/]*={0,2}$')


def base64_to_content_file(data: str) -> ContentFile:
    if not isinstance(data, str) or ';base64,' not in data:
        raise serializers.ValidationError("Invalid input format")

    parts = data.split(';base64,')
    if len(parts) != 2:
        raise serializers.ValidationError("Invalid base64 data")

    format_, imgstr = parts
    if "/" not in format_:
        raise serializers.ValidationError("Invalid MIME type")

    ext = format_.split('/')[-1]

    if len(imgstr) % 4 != 0 or not BASE64_RE.match(imgstr):
        raise serializers.ValidationError("Invalid base64 string")

    decoded = base64.b64decode(imgstr)
    return ContentFile(decoded, name=f"{uuid.uuid4()}.{ext}")
