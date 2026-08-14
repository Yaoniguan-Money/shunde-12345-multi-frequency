import re

from backend.app.domain.analysis import SegmentType, TextSegment

_LABELS: tuple[tuple[re.Pattern[str], SegmentType], ...] = (
    (re.compile(r"(?:问题|投诉|反映|情况)\s*[：:]", re.IGNORECASE), SegmentType.COMPLAINT),
    (re.compile(r"(?:历史|此前|之前|曾经)\s*[：:]", re.IGNORECASE), SegmentType.HISTORY),
    (
        re.compile(r"(?:部门回复|处理情况|办理情况|答复意见|回复)\s*[：:]", re.IGNORECASE),
        SegmentType.DEPARTMENT_REPLY,
    ),
    (re.compile(r"(?:诉求|要求|希望|请求)\s*[：:]", re.IGNORECASE), SegmentType.CURRENT_REQUEST),
)
_SENTENCE_BOUNDARY = re.compile(r"(?<=[。！？；!?;])|\r?\n+")


class RuleBasedWorkOrderSegmenter:
    """Split text into typed, offset-preserving segments without changing raw content."""

    def segment(self, title: str | None, content: str) -> tuple[TextSegment, ...]:
        text = content.strip()
        _ = title
        if not text:
            return ()
        labelled = self._labelled_segments(text)
        if labelled:
            return self._renumber(labelled)
        pieces: list[tuple[SegmentType, str, int, int]] = []
        for match in _SENTENCE_BOUNDARY.split(text):
            if not match or not match.strip():
                continue
            start = text.find(match, pieces[-1][3] if pieces else 0)
            end = start + len(match)
            pieces.append((self._infer_type(match), match.strip(), start, end))
        if not pieces:
            pieces.append((SegmentType.COMPLAINT, text, 0, len(text)))
        return self._renumber(pieces)

    @staticmethod
    def _labelled_segments(text: str) -> list[tuple[SegmentType, str, int, int]]:
        matches: list[tuple[int, int, SegmentType]] = []
        for pattern, segment_type in _LABELS:
            matches.extend(
                (match.start(), match.end(), segment_type) for match in pattern.finditer(text)
            )
        if not matches:
            return []
        matches.sort(key=lambda item: item[0])
        pieces: list[tuple[SegmentType, str, int, int]] = []
        for index, (_start, body_start, segment_type) in enumerate(matches):
            body_end = matches[index + 1][0] if index + 1 < len(matches) else len(text)
            body = text[body_start:body_end].strip()
            if body:
                pieces.append((segment_type, body, body_start, body_end))
        return pieces

    @staticmethod
    def _infer_type(text: str) -> SegmentType:
        if re.search(r"历史|此前|之前|曾经", text):
            return SegmentType.HISTORY
        if re.search(r"部门回复|处理情况|办理情况|答复|回复", text):
            return SegmentType.DEPARTMENT_REPLY
        if re.search(r"诉求|要求|希望|请求", text):
            return SegmentType.CURRENT_REQUEST
        return SegmentType.COMPLAINT

    @staticmethod
    def _renumber(
        pieces: list[tuple[SegmentType, str, int, int]],
    ) -> tuple[TextSegment, ...]:
        return tuple(
            TextSegment(segment_type, text, ordinal, start, end)
            for ordinal, (segment_type, text, start, end) in enumerate(pieces)
        )
