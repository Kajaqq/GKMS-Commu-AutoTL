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
This script uses the `config/config.py` file to set non-sensitive configuration variables. 

For API keys, it uses `.env` 

It supports both Google AI Studio and Vertex AI(now Gemini Enterprise Agent Platform) API.

### For Google AI Studio usage:
Rename `.env.example` to `.env` 

Set the `GEMINI_API_KEY` variable in the `.env` file.

### For Vertex AI/Gemini Enterprise usage:
Rename `.env.example` to `.env` 
Setup gcloud CLI and [Authenticate to the Platform](https://docs.cloud.google.com/docs/authentication/set-up-adc-local-dev-environment)

Then set the `GOOGLE_GENAI_USE_ENTERPRISE` variable to `True` in the `.env` file

### Other important configuration
Depending on your API tier, your rate limits may vary.

The script uses AI Studio free tier limits by default.

To use the paid tier limits,  set the `PAID_TIER` variable in the `.env` file to `True` 

This will increase the limits to Tier 1 ones.

The default limits are as follows:
```
    Limit - Free Tier / Tier 1
    
    Requests per minute (GEMINI_RPM_LIMIT):
        Flash models:                              5 / 1000
        Flash Lite models:                       15 / 4000
        Pro models:                              0 / 25
    Tokens per minute (GEMINI_TPM_LIMIT):
        Flash models:                       250 000 / 2 000 000
        Flash Lite models:                 250 000 / 4 000 000
        Pro models:                             0 / 2 000 000
    Requests per day (GEMINI_RPD_LIMIT):
        Flash models:                          20 / 10 000
        Flash Lite models:                   500 / 150 000
        Pro models:                           0 / 250
```


## TODO:
  - ~~Unslopify the `process_excel_files.py`~~  Done, moved to a WorkbookTranslator class.
  - ~~Load the speaking styles dynamically, based on which characters are in a given commu.~~ Done.
  - ~~Add a QC gate to check if the rules are followed~~ Done, migrated to Pydantic for validation.
  - ~~Improve the translator logic:~~ Done
    - ~~Allow translating multiple files in parallel.~~  
      - ~~Show visible progress.~~ 
      - ~~Implement rate limit logic~~
    - ~~Add retry logic~~ 
    - ~~Add better error handling.~~ 
  - ~~Add a better way to detect Vertex AI support.~~ Done.
  - Add a way to sync with Google Sheets.
  