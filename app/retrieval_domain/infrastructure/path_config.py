"""Retrieval-owned default paths for benchmark and legacy compatibility code."""

from __future__ import annotations

import os


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
OUTPUTS_DIR = os.path.join(PROJECT_ROOT, "outputs")
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")

LEGACY_SESSIONS_PATH = os.path.join(DATA_DIR, "sample_memory_sessions.json")
LEGACY_MEMORIES_PATH = os.path.join(DATA_DIR, "legacy_extracted_memories.json")
PROTECTED_LEGACY_CHROMA_DIR = os.path.join(DATA_DIR, "protected_legacy_chroma_db")
LEGACY_MEMORY_COLLECTION = "legacy_memories"

LEGACY_DUMMY_SESSIONS_PATH = os.path.join(DATA_DIR, "dummy_large_session_history.json")
LEGACY_EXTRACTED_MEMORIES_PATH = os.path.join(DATA_DIR, "extracted_memories.json")
LEGACY_CHROMA_DIR = os.path.join(DATA_DIR, "chroma_db")
LEGACY_COLLECTION = "memories"

FORGETTING_QUESTIONS_PATH = os.path.join(DATA_DIR, "forgetting_test_questions.json")
CHAT_HISTORY_PATH = os.path.join(DATA_DIR, "chat_history.json")
