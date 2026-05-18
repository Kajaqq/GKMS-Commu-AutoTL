# --- config.py ---
# This file contains configuration variables for the Excel translation script.

# IMPORTANT: Replace with your actual values
# Your Google AI Studio API Key for Gemini
GEMINI_API_KEY = 'API_KEY'

# The local folder path containing the Excel files (.xlsx) you want to translate
SOURCE_FOLDER_PATH = 'IN'

# The local folder path where you want to save the translated Excel files
# This folder will be created if it doesn't exist.
OUTPUT_FOLDER_PATH = 'OUT'

# The target language for translation (e.g., 'English')
TARGET_LANGUAGE = 'English'

# The source language (explicitly Japanese as requested)
SOURCE_LANGUAGE = 'Japanese'

# The Gemini model to use (using the specified preview model)
GEMINI_MODEL = 'gemini-3.1-flash-lite-preview'

# Temperature for translation (0.0 to 1.0, lower is less random)
TEMPERATURE = 0.2

# Headers for the source and target columns
SOURCE_HEADER = "text"
TARGET_HEADER = "translated text"

# Header for the speaker identification column
SPEAKER_HEADER = "translated name"

# Header for the message type column (assuming column A)
TYPEMESSAGE_HEADER = "type"

# Note: Formatting configuration is now in formatting.py
