"""Safe HTML formatting and splitting for readings delivered to the MAX chat."""
from html import escape
import re


def chat_message_chunks(text, positions=(), limit=3800):
    labels = sorted(set(positions) | {'Ваш расклад', 'Уточнение', 'Общее толкование', 'Совет', 'Ситуация', 'Возможное развитие', 'Главное', 'Итог'}, key=len, reverse=True)
    heading = re.compile(r'^(\s*)(' + '|'.join(re.escape(label) for label in labels) + r')(?=\s*[:—–-]|\s*$)', re.MULTILINE | re.IGNORECASE)

    def render(raw):
        # Escape the model/user text before adding our own bounded heading tags.
        safe = escape(raw.replace('**', ''))
        return heading.sub(lambda match: match[1] + '<b>' + match[2] + '</b>', safe)

    chunks = []
    remaining = str(text)
    while remaining:
        end = min(3000, len(remaining))
        while len(render(remaining[:end])) > limit:
            end //= 2
            if not end:
                raise ValueError('Message limit is too small')
        if end < len(remaining):
            boundary = remaining.rfind('\n', end // 2, end)
            if boundary < 0:
                boundary = remaining.rfind(' ', end // 2, end)
            if boundary >= 0:
                end = boundary + 1
        chunks.append(render(remaining[:end]))
        remaining = remaining[end:]
    return chunks
