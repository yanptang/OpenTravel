from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import PlannerConfig


@dataclass(frozen=True)
class RetrievalChunk:
    source: str
    title: str
    score: float
    text: str


def build_retrieval_context(
    request: dict[str, Any],
    config: PlannerConfig,
) -> dict[str, Any] | None:
    if not config.use_rag:
        return None

    rag_dir = Path(config.rag_dir).resolve() if config.rag_dir else (Path(__file__).resolve().parents[1] / "knowledge")
    if not rag_dir.exists():
        return None

    chunks = _load_chunks(rag_dir)
    if not chunks:
        return None

    query_text = _build_query_text(request)
    query_tokens = _tokenize(query_text)
    destination = str(request.get("destination", "")).strip()
    origin_city = str(request.get("origin_city", "")).strip()

    scored: list[RetrievalChunk] = []
    for source, title, text in chunks:
        score = _score_chunk(
            text=text,
            title=title,
            query_tokens=query_tokens,
            destination=destination,
            origin_city=origin_city,
        )
        if score <= 0:
            continue
        scored.append(RetrievalChunk(source=source, title=title, score=round(score, 4), text=text))

    if not scored:
        return None

    scored.sort(key=lambda item: item.score, reverse=True)
    top_k = max(1, config.rag_top_k)
    selected = scored[:top_k]
    return {
        "query_text": query_text,
        "rag_dir": str(rag_dir),
        "selected_chunks": [
            {
                "source": chunk.source,
                "title": chunk.title,
                "score": chunk.score,
                "text": chunk.text,
            }
            for chunk in selected
        ],
    }


def format_retrieval_context(context: dict[str, Any] | None) -> str:
    if not context or not context.get("selected_chunks"):
        return "No external travel knowledge retrieved."

    lines = ["Reference travel knowledge snippets:"]
    for idx, chunk in enumerate(context["selected_chunks"], start=1):
        lines.append(
            f"[{idx}] {chunk['title']} | source={chunk['source']} | score={chunk['score']}\n"
            f"{chunk['text']}"
        )
    return "\n\n".join(lines)


def _load_chunks(rag_dir: Path) -> list[tuple[str, str, str]]:
    chunks: list[tuple[str, str, str]] = []
    for path in sorted(rag_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".txt", ".json"}:
            continue
        if path.name.lower() == "readme.md":
            continue

        if path.suffix.lower() == ".json":
            chunks.extend(_load_json_chunks(path, rag_dir))
            continue

        raw = path.read_text(encoding="utf-8")
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", raw) if part.strip()]
        if not paragraphs:
            continue
        title = paragraphs[0].lstrip("# ").strip() or path.stem
        for idx, paragraph in enumerate(paragraphs[1:] or paragraphs, start=1):
            chunks.append((str(path.relative_to(rag_dir)), f"{title} / chunk {idx}", paragraph))
    return chunks


def _load_json_chunks(path: Path, rag_dir: Path) -> list[tuple[str, str, str]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return []
    chunks: list[tuple[str, str, str]] = []
    for idx, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", f"{path.stem} / chunk {idx}")).strip()
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        chunks.append((str(path.relative_to(rag_dir)), title, text))
    return chunks


def _build_query_text(request: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ["origin_city", "destination", "arrival_mode", "transport_mode", "budget_level", "notes", "special_requirements"]:
        value = request.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    must_do = request.get("must_do", [])
    if isinstance(must_do, list):
        parts.extend(str(item).strip() for item in must_do if str(item).strip())
    return "\n".join(parts)


def _score_chunk(
    *,
    text: str,
    title: str,
    query_tokens: set[str],
    destination: str,
    origin_city: str,
) -> float:
    haystack = f"{title}\n{text}"
    haystack_lower = haystack.lower()
    tokens = _tokenize(haystack)
    overlap = len(query_tokens & tokens)

    score = float(overlap)
    if destination and destination.lower() in haystack_lower:
        score += 6.0
    if origin_city and origin_city.lower() in haystack_lower:
        score += 2.0
    if any(token in haystack_lower for token in ["must-do", "highlights", "avoid", "logistics", "tips"]):
        score += 0.5
    return score


def _tokenize(text: str) -> set[str]:
    ascii_tokens = {token.lower() for token in re.findall(r"[A-Za-z0-9_]+", text)}
    zh_tokens = {token for token in re.findall(r"[\u4e00-\u9fff]{2,}", text)}
    return ascii_tokens | zh_tokens
