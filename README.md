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

It supports both Google AI Studio and Vertex AI (now Gemini Enterprise Agent Platform) API.

### For Google AI Studio usage:
Rename `.env.example` to `.env` 

Set the `GEMINI_API_KEY` variable in the `.env` file.

### For Vertex AI/Gemini Enterprise usage:
Rename `.env.example` to `.env` 
Setup gcloud CLI and [Authenticate to the Platform](https://docs.cloud.google.com/docs/authentication/set-up-adc-local-dev-environment)

Then set the `GOOGLE_GENAI_USE_ENTERPRISE` variable to `True` in the `.env` file

### Other important configuration

#### The below only applies to Google AI Studio API as Vertex doesn't have rate limits, it instead uses something called a *Dynamic Shared Quota*

Depending on your API tier, your rate limits may vary.  The script uses AI Studio free tier limits by default.

Set `GEMINI_MODEL` in `.env` to choose the primary model. You can also set `FALLBACK_MODEL` to one or two fallback
models separated by a comma. If the script reaches the local daily request limit for the current model, it asks whether
to switch to the next fallback model and then uses that model's local rate limits.

To use the paid tier limits, set the `PAID_TIER` variable in the `.env` file to `True`. 
This will increase the limits to Tier 1 ones.

The default limits are as follows:
```
Requests per minute (GEMINI_RPM_LIMIT)
  Model               Free Tier  Tier 1
  Flash models        5          1 000
  Flash Lite models   15         4 000
  Pro models          0          25

Tokens per minute (GEMINI_TPM_LIMIT)
  Model               Free Tier  Tier 1
  Flash models        250 000    2 000 000
  Flash Lite models   250 000    4 000 000
  Pro models          0          2 000 000

Requests per day (GEMINI_RPD_LIMIT)
  Model               Free Tier  Tier 1
  Flash models        20         10 000
  Flash Lite models   500        150 000
  Pro models          0          250
```

## TODO:
1. [x] Rewrite `process_excel_files.py` 
2. [x] Load the speaking styles dynamically, based on which characters are in a given commu.
3. [x] Add a QC gate to check if the rules are followed
4. [x] Improve the translator logic:
    - [x] Allow translating multiple files in parallel.  
      - [x] Show visible progress.
      - [x] Implement rate limit logic
    - [x] Add retry logic 
    - [x] Add better error handling.
5. [x] Add a better way to detect Vertex AI support.
6. [ ] Add a way to sync with Google Sheets.
