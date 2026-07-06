import re
import google.generativeai as genai
from google.cloud import firestore

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    RAG_CHUNK_OVERLAP,
    RAG_CHUNK_SIZE,
    RAG_MAX_CONTEXT_CHARS,
    RAG_MIN_QUERY_TERM_LEN,
)
from models import Document, SiteConfig

MAX_HISTORY_TURNS = 6


def _extract_terms(*texts: str) -> set[str]:
    terms: set[str] = set()
    for text in texts:
        for token in re.findall(r"[a-zA-Z0-9_\-]+", text.lower()):
            if len(token) >= RAG_MIN_QUERY_TERM_LEN:
                terms.add(token)
    return terms


def _split_into_chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _format_doc_section(doc: Document, content: str, label: str = "Full content") -> str:
    return (
        f"--- Document: {doc.original_filename} ---\n"
        f"Description: {doc.description or 'No description'}\n"
        f"File type: {doc.file_type}\n"
        f"{label}:\n{content}"
    )


def _score_chunk(chunk: str, query_terms: set[str]) -> float:
    if not query_terms:
        return 0.0
    chunk_lower = chunk.lower()
    score = 0.0
    for term in query_terms:
        if term in chunk_lower:
            score += chunk_lower.count(term)
    return score


def _build_profile_context(config: SiteConfig) -> str:
    return (
        f"Site Owner Profile:\n"
        f"- Name: {config.owner_name}\n"
        f"- Role: {config.role}\n"
        f"- Experience: {config.experience}\n"
        f"- Email: {config.contact_email or 'N/A'}\n"
        f"- Phone: {config.contact_phone or 'N/A'}\n"
        f"- LinkedIn: {config.contact_linkedin or 'N/A'}\n"
    )


def _build_full_documents_context(docs: list[Document]) -> tuple[str, int]:
    sections: list[str] = []
    total_chars = 0
    for doc in docs:
        text = (doc.extracted_text or "").strip()
        if not text:
            continue
        section = _format_doc_section(doc, text)
        sections.append(section)
        total_chars += len(section)
    body = "\n\n".join(sections) if sections else "No document content available yet."
    return body, total_chars


def _build_retrieved_context(
    docs: list[Document], query_terms: set[str], budget: int
) -> str:
    scored_chunks: list[tuple[float, Document, int, str]] = []

    for doc in docs:
        text = (doc.extracted_text or "").strip()
        if not text:
            continue
        chunks = _split_into_chunks(text, RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP)
        for index, chunk in enumerate(chunks):
            score = _score_chunk(chunk, query_terms)
            scored_chunks.append((score + 0.01, doc, index, chunk))

    if not scored_chunks:
        return "No document content available yet."

    scored_chunks.sort(key=lambda item: (-item[0], item[1].upload_date, item[2]))

    selected: list[str] = []
    used_chars = 0
    docs_included: set[str] = set()

    for score, doc, index, chunk in scored_chunks:
        if score <= 0 and docs_included and len(docs_included) >= len(docs):
            break
        section = _format_doc_section(
            doc,
            chunk,
            label=f"Relevant section {index + 1}",
        )
        if used_chars + len(section) > budget:
            if not docs_included:
                remaining = budget - used_chars
                if remaining > 500:
                    trimmed = chunk[: max(remaining - 200, 0)]
                    if trimmed:
                        selected.append(
                            _format_doc_section(
                                doc,
                                trimmed + "…",
                                label=f"Relevant section {index + 1} (truncated)",
                            )
                        )
            continue
        selected.append(section)
        used_chars += len(section)
        docs_included.add(doc.id or "")

    if not selected:
        return "No document content available yet."

    return "\n\n".join(selected)


def build_context(db: firestore.Client, message: str, history: list[dict]) -> str:
    doc_ref = db.collection('site_config').document('1')
    doc_snap = doc_ref.get()
    if not doc_snap.exists:
        config = SiteConfig(id="1")
        doc_ref.set(config.model_dump(mode='json'))
    else:
        config = SiteConfig(**doc_snap.to_dict())

    profile = _build_profile_context(config)

    docs_snap = db.collection('documents').get()
    all_docs = [Document(**d.to_dict()) for d in docs_snap]
    all_docs.sort(key=lambda d: d.upload_date, reverse=True)

    full_body, full_chars = _build_full_documents_context(all_docs)

    profile_budget = len(profile) + 500
    doc_budget = max(RAG_MAX_CONTEXT_CHARS - profile_budget, 10_000)

    recent_user_messages = [
        turn.get("content", "")
        for turn in history[-4:]
        if turn.get("role") == "user"
    ]
    query_terms = _extract_terms(message, *recent_user_messages)

    if full_chars <= doc_budget:
        docs_header = f"Architecture Documents ({len(all_docs)} total, full text included):\n"
        docs_context = full_body
    else:
        docs_header = (
            f"Architecture Documents ({len(all_docs)} total, "
            f"retrieved relevant sections from full corpus):\n"
        )
        docs_context = _build_retrieved_context(all_docs, query_terms, doc_budget)

    return f"{profile}\n{docs_header}{docs_context}"


def generate_reply(db: firestore.Client, message: str, history: list[dict]) -> str:
    if not GEMINI_API_KEY:
        return "AI chat is not configured. Please set the GEMINI_API_KEY environment variable."

    context = build_context(db, message, history)

    system_prompt = (
        "You are a helpful AI assistant for an Architecture Document Showcase portfolio website. "
        "Answer questions about the site owner's professional experience and uploaded architecture "
        "documents using the context below. The context includes the full extracted text of "
        "uploaded documents when possible. Reference specific documents by name when helpful. "
        "If the answer is not in the context, say so honestly. "
        "Be concise, professional, and friendly.\n\n"
        f"CONTEXT:\n{context}"
    )

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL)

        chat_history = []
        trimmed = history[-MAX_HISTORY_TURNS * 2 :]
        for turn in trimmed:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if not content:
                continue
            gemini_role = "model" if role == "assistant" else "user"
            chat_history.append({"role": gemini_role, "parts": [content]})

        chat = model.start_chat(history=chat_history)
        full_message = f"{system_prompt}\n\nUser question: {message}"
        response = chat.send_message(full_message, request_options={"timeout": 60})
        return response.text or "I couldn't generate a response. Please try again."
    except Exception as exc:
        return f"AI chat error: {exc}"
