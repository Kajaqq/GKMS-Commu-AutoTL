# GKMS-Commu-AutoTL

A script to automatically translate Gakumas commus using the Gemini API.
Work in progress.

## Requirements
This script uses the uv package manager.
Install it using `pip install uv` or natively, according to the [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/).
Then, install the required dependencies using `uv sync`.

## Usage
Put the xlsx files in the 'IN' directory, then run the script.
```
uv run process_excel_files.py
```
Outputs the translated files in the 'OUT' directory.

## Configuration
This script uses the `config.py` file to set non-sensitive configuration variables. 

For API keys, it uses `.env` 

It supports both Google AI Studio and Vertex AI API.

### For Google AI Studio usage:
Rename `.env.example` to `.env` 

Set the `AI_STUDIO_API_KEY` variable in the `.env` file.

### For Vertex AI usage:
Rename `.env.example` to `.env` 

Set the `GOOGLE_CLOUD_PROJECT` variable in the `.env` file.

## TODO:
  - ~~Unslopify the `process_excel_files.py`~~  Mostly done.
  - ~~Load the speaking styles dynamically, based on which characters are in a given commu.~~ Done.
  - ~~Add a QC gate to check if the rules are followed~~ Mostly done, moved to Pydantic verification.
  - Improve the translator logic:
    - Allow translating multiple files in parallel.
    - Show visible progress for multiple file processing.
    - Add better error handling.
    - Implement rate limit avoidance logic
    - Add a better way to detect Vertex AI support.
  - Add a way to sync with Google Sheets.
  