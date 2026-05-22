# GKMS-Commu-AutoTL

A script to automatically translate Gakumas commus using the Gemini API.
Work in progress.

## Requirements
This script uses the uv package manager.
Install it using `pip install uv` or natively according to the [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/).
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
  - ~~Unslopify the `process_excel_files.py`~~  In progress.
  - ~~Load the speaking styles dynamically, based on which characters are in a given commu.~~ Done.
  - Improve the translator logic to allow translating multiple files in parallel.
  - Add a progress bar to the script.
  - Add a QC gate to check if the rules are followed
  - Add a way to sync with Google Sheets.