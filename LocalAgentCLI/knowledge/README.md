# Local Knowledge Base

This folder stores lightweight local travel knowledge for the first RAG pass.

Guidelines:

- Keep each file destination-focused.
- Prefer short factual or planning-oriented paragraphs.
- Include both highlights and logistics hints.
- Avoid hard-coded schedules that may go stale quickly.

Suggested structure:

- one file per destination or route
- one paragraph per reusable knowledge snippet
- mention place aliases in English and Chinese when useful

The retriever currently scores chunks using destination matches and keyword overlap.
