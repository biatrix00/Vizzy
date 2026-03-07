"""
scraper/pdf_parser.py — OCR for scanned VTU timetable PDFs using Gemini Vision.

Used for the "Nice to Have" timetable parsing feature (PDR section 9).

Logic (no implementation yet):
1. Receive a PDF file sent to the bot by a group admin
2. Use Gemini Vision (via ai/gemini.py) to OCR the scanned image PDF
3. Extract: subject names, exam dates, exam times from the OCR output
4. Parse the extracted text into a structured dict keyed by branch/semester
5. Return structured timetable data to commands.py for distribution

parse_timetable_pdf(pdf_bytes):
    Main function. Takes raw PDF bytes, returns structured timetable dict or raises.

No logic implemented yet — this is a stub.
"""
