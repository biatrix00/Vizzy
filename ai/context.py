"""
ai/context.py — Builds the context string injected into every Gemini prompt.

The SDR requires that every Gemini call includes VTU context so answers
are relevant and grounded in up-to-date local data.

Functions to implement (stubs only):
- build_prompt_context() -> str
    Assembles a context block containing:
    1. A short system description: "You are Vizzy, a VTU student assistant bot."
    2. The latest 5 VTU circulars from db/circulars.py (title + date)
    3. Current VTU scheme information (hardcoded reference data)
    Returns a single formatted string prepended to every user question
    before it is passed to ai/gemini.py.

Example output (rough format):
    You are Vizzy, a helpful assistant for VTU students.
    
    Latest VTU Updates:
    - [2024-01-15] Revised exam schedule for Jan 2024 exams: https://...
    - [2024-01-10] Academic calendar 2024: https://...
    
    VTU Scheme: CBCS scheme applies to students admitted from 2015 onwards.
    Current batches: 2021 (8th sem), 2022 (6th sem), 2023 (4th sem), 2024 (2nd sem)

No logic implemented yet — this is a stub.
"""
