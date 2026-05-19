import re
from pathlib import Path

import openpyxl
from openpyxl.cell.cell import Cell

# --- Import Configuration ---
from config import TranslatorConfig, ExcelConfig
from dictionary import NAME_TERM_TRANSLATIONS
from character_styles import CHARACTER_SPEAKING_STYLES
from prompts import LINE_FORMAT_TEMPLATE, TRANSLATION_PROMPT_TEMPLATE
from text_utils import normalize_cell, safe_str
from formatting import wrap_text
from translator import translate_batch_with_gemini

HEADER_SEARCH_ROWS = 10


# --- Header Locating ---
def locate_header_row(sheet) -> tuple[int, dict[str, int]] | None:
    max_search = min(sheet.max_row, HEADER_SEARCH_ROWS)
    source_header = ExcelConfig.SOURCE_HEADER.lower()
    for row_index in range(1, max_search + 1):
        row_cells = sheet[row_index]
        normalized = [normalize_cell(cell.value) for cell in row_cells]
        if source_header in normalized:
            header_map = {
                name: idx + 1  # 1-based column index for sheet.cell()
                for idx, name in enumerate(normalized)
                if name
            }
            return row_index, header_map
    return None

# --- API Calling ---
def request_translations_from_api(api_lines_formatted):
    """Builds the prompt, calls the Gemini API and parses the response.

    Returns a tuple of (raw_response_text, parsed_translations_dict).
    """
    character_styles_list_str = "\n".join(
        f"- {name}: {style}"
        for name, style in CHARACTER_SPEAKING_STYLES.items()
    )

    batch_prompt = TRANSLATION_PROMPT_TEMPLATE.format(
        source_lang=TranslatorConfig.SOURCE_LANGUAGE,
        target_lang=TranslatorConfig.TARGET_LANGUAGE,
        character_styles_list=character_styles_list_str or "None provided.",
        lines_to_translate="\n".join(api_lines_formatted),
    )

    print(f"Sending {len(api_lines_formatted)} lines to Gemini...")
    translated_batch_text = translate_batch_with_gemini(batch_prompt)

    parsed_api_translations = {}
    if not translated_batch_text.startswith("BATCH_TRANSLATION_ERROR"):
        translated_lines = re.findall(
            r"Line\s*(\d+)\s*[:.]?\s*(.*?)(?=\nLine\s*\d+\s*[:.]?|\Z)",
            translated_batch_text,
            re.DOTALL,
        )
        parsed_api_translations = {
            int(num): text.strip() for num, text in translated_lines
        }

    return translated_batch_text, parsed_api_translations

# --- XLSX Processing ---
def process_workbook(source_file_path: Path, output_file_path: Path) -> bool:
    """Processes a single Excel workbook: reads, translates, and saves.

    Returns True if the file was processed and saved successfully.
    """
    file_name = source_file_path.name
    workbook = openpyxl.load_workbook(source_file_path)
    output_file_exists = output_file_path.exists()
    should_save = False
    completed = False
    try:
        sheet = workbook.active
        if sheet is None:
            print("Skipping: workbook has no active sheet.")
            return False

        header_info = locate_header_row(sheet)
        if header_info is None:
            print(
                f"Skipping: Header '{ExcelConfig.SOURCE_HEADER}' not found "
                f"or file is empty."
            )
            return False

        header_row, header_map = header_info

        source_col = header_map.get(ExcelConfig.SOURCE_HEADER.lower())
        target_col = header_map.get(ExcelConfig.TARGET_HEADER.lower())
        speaker_col = header_map.get(ExcelConfig.SPEAKER_HEADER.lower())
        typemessage_col = header_map.get(ExcelConfig.TYPEMESSAGE_HEADER.lower())

        if source_col is None:
            print(f"Error: Source header '{ExcelConfig.SOURCE_HEADER}' missing.")
            return False
        if target_col is None:
            print(f"Error: Target header '{ExcelConfig.TARGET_HEADER}' missing.")
            return False
        should_save = True

        # Collect rows that need translation
        dict_translations: dict[int, str] = {}
        api_lines_formatted: list[str] = []
        pending_rows: list[tuple[int, Cell, str]] = []  # (line_number, target_cell, message_type)

        wanted_cols = [source_col, target_col]
        if speaker_col:
            wanted_cols.append(speaker_col)
        if typemessage_col:
            wanted_cols.append(typemessage_col)
        min_col = min(wanted_cols)
        max_col = max(wanted_cols)

        def cell_at(row, column):
            return row[column - min_col]

        first_data_row = header_row + 1
        for line_number, row in enumerate(
            sheet.iter_rows(min_row=first_data_row, min_col=min_col, max_col=max_col),
            start=1,
        ):
            source_text = safe_str(cell_at(row, source_col).value)
            target_cell = cell_at(row, target_col)
            existing_translation = safe_str(target_cell.value)
            speaker_info = (
                safe_str(cell_at(row, speaker_col).value)
                if speaker_col
                else ""
            )
            message_type = (
                safe_str(cell_at(row, typemessage_col).value).lower()
                if typemessage_col
                else ""
            )

            needs_translation = source_text != "" and (
                existing_translation == ""
                or existing_translation.startswith("TRANSLATION_ERROR")
            )
            if not needs_translation:
                continue

            if source_text in NAME_TERM_TRANSLATIONS:
                dict_translations[line_number] = NAME_TERM_TRANSLATIONS[source_text]
            else:
                api_lines_formatted.append(
                    LINE_FORMAT_TEMPLATE.format(
                        line_number=line_number,
                        speaker=speaker_info or "Unknown",
                        text=source_text,
                    )
                )
            pending_rows.append((line_number, target_cell, message_type))

        if not pending_rows and output_file_path.exists():
            print(f"No translations needed; refreshing output: {file_name}")

        # Call the API if there are non-dictionary lines, then write results back
        if pending_rows:
            translated_batch_text = ""
            parsed_api_translations: dict[int, str] = {}

            if api_lines_formatted:
                translated_batch_text, parsed_api_translations = (
                    request_translations_from_api(api_lines_formatted)
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
        completed = True
    finally:
        if should_save and (completed or not output_file_exists):
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
        print(f"Error: Source folder not found at {source_folder}")
        return processed_count

    output_folder.mkdir(parents=True, exist_ok=True)

    items = sorted(source_folder.glob("*.xlsx"))
    if not items:
        print("No Excel files found.")
        return processed_count

    for source_file_path in items:
        output_file_path = output_folder / source_file_path.name
        file_name = source_file_path.name
        print(f"\n--- Processing file: {file_name} ---")

        try:
            if process_workbook(source_file_path, output_file_path):
                processed_count += 1
        except Exception as e:
            print(f"Error processing {file_name}: {e}")

    return processed_count


# --- Run the script ---
if __name__ == "__main__":
    print("Starting Gemini Excel Batch Translator script...")
    total_processed = process_excel_files_in_folder()
    if total_processed > 0:
        print(f"\nScript finished. Processed {total_processed} files.")
