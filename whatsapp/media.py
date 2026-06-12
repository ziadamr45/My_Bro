"""
WhatsApp Media Processing Module
==================================
Media download, processing, and sending functions for WhatsApp bot.

Extracted from whatsapp_webhook.py for modularity.
Split into sub-modules for maintainability:
  - whatsapp/media_image.py      → Image generation & editing
  - whatsapp/media_download.py   → Video download & quality selection
  - whatsapp/media_processing.py → Audio/video processing & analysis

This file is a thin shim that re-exports everything for backward compatibility.
"""

# ═══════════════════════════════════════
# Image Generation & Editing
# ═══════════════════════════════════════
from whatsapp.media_image import (
    _translate_prompt_to_english,
    _generate_and_send_image,
    _edit_and_send_image,
)

# ═══════════════════════════════════════
# Video Download & Quality Selection
# ═══════════════════════════════════════
from whatsapp.media_download import (
    _download_threads_media_wa,
    _show_quality_selection,
    _show_quality_selection_for_search,
    _download_and_send_video,
)

# ═══════════════════════════════════════
# Audio/Video Processing & Analysis
# ═══════════════════════════════════════
from whatsapp.media_processing import (
    _transcribe_audio,
    _download_wa_media_base64,
    _analyze_image,
    _analyze_document,
    _execute_photo_search,
)
