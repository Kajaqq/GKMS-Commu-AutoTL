from pathlib import Path

import openpyxl
from openpyxl.cell.cell import Cell, MergedCell

from character_styles import CHARACTER_SPEAKING_STYLES

# --- Import Configuration ---
from config import ExcelConfig, TranslatorConfig
from dictionary import NAME_TERM_TRANSLATIONS
from formatting import wrap_text
from prompts import LINE_FORMAT_TEMPLATE, TRANSLATION_PROMPT_TEMPLATE
from text_utils import normalize_cell, parse_translation_response, safe_str
from translator import translate_batch_with_gemini

# --- Sheet utils ---
expected_header = [
    ExcelConfig.TYPE,
    ExcelConfig.ORIGINAL_SPEAKER,
    ExcelConfig.TRANSLATED_SPEAKER,
    ExcelConfig.SOURCE,
    ExcelConfig.TARGET,
]

def validate_header_row(sheet) -> None:
    # Check if the header row is present and contains the expected headers
    sheet_header = [normalize_cell(cell.value) for cell in sheet[1]]
    if sheet_header != expected_header:
        raise ValueError(
            f"Header row has incorrect headers: "
            f"Expected headers: {', '.join(expected_header)}."
            f"File headers: {', '.join(sheet_header)}"
        )


# --- API Calling ---

def find_glossary_entries(source_texts: list[str]) -> dict[str, str]:
    joined_source = "\n".join(source_texts)
    # Get which entries from glossary appear in the text, return only them
    return {source: translation for source, translation in NAME_TERM_TRANSLATIONS.items() if source in joined_source}

def find_character_styles(character_names: set[str]) -> dict[str, str]:
    return {
        name: style
        for name, style in CHARACTER_SPEAKING_STYLES.items()
        if any(character_name in name for character_name in character_names)
    }

def build_translation_prompt(
    api_lines_formatted: list[str],
    glossary_entries: dict[str, str],
    character_names: set[str],
) -> str:
    character_styles = find_character_styles(character_names)
    character_styles_list_str = "\n".join(f"- {name}: {style}" for name, style in character_styles.items())
    glossary_list_str = "\n".join(f"- {source}: {translation}" for source, translation in glossary_entries.items())

    return TRANSLATION_PROMPT_TEMPLATE.format(
        source_lang=TranslatorConfig.SOURCE_LANGUAGE,
        target_lang=TranslatorConfig.TARGET_LANGUAGE,
        character_styles_list=character_styles_list_str or "None provided.",
        glossary_list=glossary_list_str or "None provided.",
        lines_to_translate="\n".join(api_lines_formatted),
    )

def request_translations_from_api(
    api_lines_formatted: list[str],
    api_line_numbers: list[int],
    glossary_entries: dict[str, str],
    character_names: set[str],
):
    """Builds the prompt, calls the Gemini API, and parses the response.

    Returns a tuple of (raw_response_text, parsed_translations_dict).
    """
    batch_prompt = build_translation_prompt(api_lines_formatted, glossary_entries, character_names)

    print(f"Sending {len(api_lines_formatted)} lines to Gemini...")
    translated_batch_text = translate_batch_with_gemini(batch_prompt)

    parsed_api_translations = {}
    if not translated_batch_text.startswith("BATCH_TRANSLATION_ERROR"):
        try:
            parsed_api_translations = parse_translation_response(
                translated_batch_text,
                api_line_numbers,
            )
        except (TypeError, ValueError) as error:
            print(f"Error parsing Gemini response: {error}")
            translated_batch_text = f"BATCH_TRANSLATION_ERROR: {error}"

    return translated_batch_text, parsed_api_translations


# --- XLSX Processing ---
def process_workbook(source_file_path: Path, output_file_path: Path) -> bool:
    """Processes a single Excel workbook: reads, translates, and saves.

    Returns True if the file was processed and saved successfully.
    """
    file_name = source_file_path.name
    workbook = openpyxl.load_workbook(source_file_path)
    sheet = workbook.active
    output_file_exists = output_file_path.exists()
    should_save = False
    completed = False
    changed = False
    try:
        if sheet is None:
            print(f"ERROR: Workbook is empty. Skipping {file_name}")
            return False

        validate_header_row(sheet)
        should_save = True

        # ---- Setup variables ----
        all_rows = sheet.iter_rows(min_row=2, min_col=1, max_col=5)  # All rows, excluding header
        api_lines_formatted: list[str] = []  # Formatted lines for translation
        api_line_numbers: list[int] = []
        api_source_texts: list[str] = []  # Source lines sent to the API, used for file-scoped glossary
        character_names: set[str] = set()
        dict_translations: dict[int, str] = {}  # The translation output
        pending_rows: list[tuple[int, Cell, str]] = []  # A list of rows that need translation

        for line_number, row in enumerate(all_rows, start=1):
            # Read each row
            message_type_cell, origin_speaker_cell, speaker_cell, source_cell, target_cell = row
            # Check if the translation cell is not a MergedCell, these cannot be wrapped, so we skip them.
            if isinstance(target_cell, MergedCell):
                print(f"WARNING: A merged translation cell was found in line {line_number}.")
                print("These can not be wrapped, skipping line.")
                continue
            # Converts None to empty string and strips leading whitespace
            source_text = safe_str(source_cell.value)
            existing_translation = safe_str(target_cell.value)
            origin_speaker_info = safe_str(origin_speaker_cell.value)
            speaker_info = safe_str(speaker_cell.value)
            message_type = safe_str(message_type_cell.value).lower()
            character_names.update(name for name in (origin_speaker_info, speaker_info) if name)

            # Check if translation is required
            needs_translation = source_text != "" and (
                existing_translation == "" or existing_translation.startswith("TRANSLATION_ERROR")
            )
            if not needs_translation:
                continue

            # If the line matches a name term exactly, don't send it to API, instead replace from dict.
            if source_text in NAME_TERM_TRANSLATIONS:
                dict_translations[line_number] = NAME_TERM_TRANSLATIONS[source_text]
            else:
                api_source_texts.append(source_text)
                api_line_numbers.append(line_number)
                api_lines_formatted.append(
                    LINE_FORMAT_TEMPLATE.format(
                        line_number=line_number,
                        speaker=speaker_info or "Unknown",
                        text=source_text,
                    )
                )

            # Save a list of rows that need translation
            pending_rows.append((line_number, target_cell, message_type))

        if not pending_rows and output_file_path.exists():
            print(f"No translations needed; leaving existing output unchanged: {file_name}")

        # Call the API and write the translated rows back
        if pending_rows:
            translated_batch_text = ""
            parsed_api_translations: dict[int, str] = {}

            if api_lines_formatted:
                glossary_entries = find_glossary_entries(api_source_texts)
                translated_batch_text, parsed_api_translations = request_translations_from_api(
                    api_lines_formatted, api_line_numbers, glossary_entries, character_names
                )

            for line_number, target_cell, message_type in pending_rows:
                if line_number in dict_translations:
                    translated_text = dict_translations[line_number]
                elif translated_batch_text.startswith("BATCH_TRANSLATION_ERROR"):
                    translated_text = translated_batch_text
                elif line_number in parsed_api_translations:
                    translated_text = parsed_api_translations[line_number]
                else:
                    translated_text = f"PARSING_ERROR: Line {line_number} missing."

                wrapped = wrap_text(translated_text, file_name, message_type)
                target_cell.value = wrapped
                changed = True
        completed = True
    # TODO: Verify this logic, should_save, completed and changed?
    finally:
        if should_save and completed and (changed or not output_file_exists):
            workbook.save(output_file_path)
            print(f"Saved: {file_name}")
    return True


# --- Main Processing Logic ---
def process_excel_files_in_folder(
    source_folder_path=TranslatorConfig.SOURCE_FOLDER_PATH,
    output_folder_path=TranslatorConfig.OUTPUT_FOLDER_PATH,
):
    """Finds and processes Excel files (.xlsx) in a given local folder."""
    processed_count = 0
    source_folder = Path(source_folder_path)
    output_folder = Path(output_folder_path)

    if not source_folder.is_dir():
        raise ValueError(f"Error: Source folder not found at {source_folder}")

    output_folder.mkdir(parents=True, exist_ok=True)

    items = sorted(source_folder.glob("*.xlsx"))
    if not items:
        print("Error: No Excel files found.")
        return processed_count

    for source_file_path in items:
        source_file_name = source_file_path.name
        output_file_path = output_folder / source_file_name
        print(f"\n--- Processing file: {source_file_name} ---")
        try:
            if process_workbook(source_file_path, output_file_path):
                processed_count += 1
        except Exception as e:
            print(f"Error processing {source_file_name}: {e}")

    return processed_count


# --- Run the script ---
if __name__ == "__main__":
    print("Starting Gakumas Commu Excel Batch Translator script...")
    total_processed = process_excel_files_in_folder()
    if total_processed > 0:
        print(f"\nScript finished. Processed {total_processed} files.")
