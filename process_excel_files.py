from pathlib import Path

import openpyxl
from openpyxl.cell.cell import Cell, MergedCell

# --- Import Configuration ---
from Models import SourceLine, TranslationPrompt, PromptReferences
from config import ExcelConfig, TranslatorConfig
from dictionary import NAME_TERM_TRANSLATIONS
from formatting import wrap_text
from text_utils import normalize_cell, safe_str
from translator import translate_batch_with_gemini
from translator_helper import parse_translation_response, get_prompt_refrences


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

def request_translations_from_api(
        source_lines: list[SourceLine],
        references: PromptReferences,
        api_line_numbers: set[int]) -> dict[int, str]:
    """Builds the prompt, calls the Gemini API, and parses the response.

    Returns parsed translations keyed by workbook line number.
    """
    batch_prompt = TranslationPrompt(
        references=references,
        lines=source_lines,
        source_lang=TranslatorConfig.SOURCE_LANGUAGE,
        target_lang=TranslatorConfig.TARGET_LANGUAGE,
    )

    print(f"Sending {len(source_lines)} lines to Gemini...")
    api_translations = translate_batch_with_gemini(batch_prompt)

    if api_translations.startswith("BATCH_TRANSLATION_ERROR"):
        raise RuntimeError(api_translations)

    return parse_translation_response(
        api_translations,
        api_line_numbers,
    )

# --- XLSX Processing ---

def process_workbook(source_file: Path, output_file :Path) -> bool:
    """Processes a single Excel workbook: reads, translates, and saves.

    Returns True if the file was processed and saved successfully.
    """
    file_name = source_file.name
    workbook = openpyxl.load_workbook(source_file)
    sheet = workbook.active
    should_save = False
    completed = False
    changed = False
    has_translation_errors = False
    try:
        if sheet is None:
            print(f"WARNING: Input file {file_name} is empty. Skipping.")
            return False

        validate_header_row(sheet)
        # TODO: First `should_save`
        should_save = True

        # ---- Setup variables ----
        all_rows = sheet.iter_rows(min_row=2, min_col=1, max_col=5)  # All rows, excluding header
        source_lines: list[SourceLine] = []  # Formatted lines for translation -- {line_num, speaker, text} format
        #TODO: Check the two below
        dict_translations: dict[int, str] = {}  # The translation output
        pending_rows: list[tuple[int, Cell, str]] = []  # A list of rows that need translation

        for line_number, row in enumerate(all_rows, start=1):

            # Read each row
            message_type_cell, origin_speaker_cell, speaker_cell, source_cell, target_cell = row

            # Check if the translation cell is not a MergedCell, these can cause issues later on, so we skip them
            if isinstance(target_cell, MergedCell):
                print(f"WARNING: A merged translation cell was found in line {line_number}.")
                print("These can not be wrapped nor written properly, skipping line.")
                continue

            # Converts None to empty string and strips leading whitespace
            
            source_text = safe_str(source_cell.value)
            existing_translation = safe_str(target_cell.value)
            speaker_info = safe_str(speaker_cell.value)
            origin_speaker_info = safe_str(origin_speaker_cell.value)
            message_type = safe_str(message_type_cell.value).lower()
            speaker = speaker_info or origin_speaker_info

            # Check if translation is required
            # Assume that if there's source_text and existing translation is empty or starts with "TRANSLATION_ERROR", it needs translation
            needs_translation = source_text != "" and (
                existing_translation == "" or existing_translation.startswith("TRANSLATION_ERROR")
            )
            if not needs_translation:
                continue

            # If the line matches a name term exactly, don't send it to API, instead replace from dict.
            normalized_source_text = source_text.replace(" ", "")
            if normalized_source_text in NAME_TERM_TRANSLATIONS:
                dict_translations[line_number] = NAME_TERM_TRANSLATIONS[normalized_source_text]
            else:
                source_line = SourceLine(line_number=line_number, speaker=speaker, text=source_text)
                source_lines.append(source_line)

            # Save a list of rows that need translation
            pending_rows.append((line_number, target_cell, message_type))

        if not pending_rows and output_file.exists():
            print(f"No translations needed; leaving existing output unchanged: {file_name}")

        # Call the API and write the translated rows back
        if pending_rows:
            parsed_api_translations: dict[int, str] = {}
            api_line_numbers = {line.line_number for line in source_lines}

            if source_lines:
                translation_references = get_prompt_refrences(source_lines)
                parsed_api_translations = request_translations_from_api(
                    source_lines=source_lines,
                    references=translation_references,
                    api_line_numbers=api_line_numbers
                )

            for line_number, target_cell, message_type in pending_rows:
                if line_number in dict_translations:
                    translated_text = dict_translations[line_number]
                elif line_number in parsed_api_translations:
                    translated_text = parsed_api_translations[line_number]
                else:
                    translated_text = f"TRANSLATION_ERROR: Line {line_number} missing from parsed API translations."

                if translated_text.startswith("TRANSLATION_ERROR"):
                    has_translation_errors = True

                wrapped = wrap_text(translated_text, file_name, message_type)
                target_cell.value = wrapped
                changed = True
        completed = True
    # TODO: Verify this logic, should_save, completed and changed?
    finally:
        if should_save and completed and (changed or not output_file.exists()):
            workbook.save(output_file)
            print(f"Saved: {file_name}")
    if has_translation_errors:
        print(f"WARNING: {file_name} is incomplete and may require a rerun due to translation errors.")
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

    commu_files = sorted(source_folder.glob("*.xlsx"))
    if not commu_files:
        print("Error: No Excel files found.")
        return processed_count

    for source_file_path in commu_files:
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
