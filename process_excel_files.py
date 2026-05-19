import os
import re
import shutil

import openpyxl
import pandas as pd

# --- Import Configuration ---
from config import TranslatorConfig, ExcelConfig
from dictionary import NAME_TERM_TRANSLATIONS
from character_styles import CHARACTER_SPEAKING_STYLES
from prompts import LINE_FORMAT_TEMPLATE, TRANSLATION_PROMPT_TEMPLATE
from formatting import *
from translator import translate_batch_with_gemini

HEADER_SEARCH_ROWS = 10


def normalize_cell(value):
    return str(value).strip().lower()


def find_column(columns, header):
    return next((col for col in columns if normalize_cell(col) == header.lower()), None)


def wrap_translation(text, file_name, message_type):
    return wrap_text(
        text,
        file_name,
        message_type,
        DEFAULT_MAX_CHARS_PER_LINE,
        DIALOGUE_TYPES,
        DEFAULT_MAX_DIALOGUE_LINE_BREAKS,
        ADV_PEVENT_PREFIX,
        ADV_PEVENT_MAX_CHARS,
        ADV_PEVENT_MAX_CHOICE_BREAKS,
        OTHER_MAX_CHARS,
        OTHER_MAX_CHOICE_BREAKS,
        ADV_UNIT_PREFIX,
        ADV_PEVENT_CHOICE_LINE1_CHARS,
        ADV_PEVENT_CHOICE_LINE2_CHARS,
        ADV_PEVENT_CHOICE_LINE3_CHARS,
    )


# --- Main Processing Logic ---
def process_excel_files_in_folder(
    source_folder_path=TranslatorConfig.SOURCE_FOLDER_PATH,
    output_folder_path=TranslatorConfig.OUTPUT_FOLDER_PATH,
):
    """Finds and processes Excel files (.xlsx) in a given local folder."""
    processed_count = 0
    if not os.path.isdir(source_folder_path):
        print(f"Error: Source folder not found at {source_folder_path}")
        return processed_count
    if not os.path.exists(output_folder_path):
        os.makedirs(output_folder_path)
    items = [f for f in os.listdir(source_folder_path) if f.endswith(".xlsx")]
    if not items:
        print("No Excel files found.")
        return processed_count

    for item in items:
        source_file_path = os.path.join(source_folder_path, item)
        output_file_path = os.path.join(output_folder_path, item)
        file_name = item
        print(f"\n--- Processing file: {file_name} ---")

        try:
            df_raw = pd.read_excel(source_file_path, sheet_name=0, header=None)

            if df_raw.empty:
                continue

            header_row_index = None
            header_row_values = None

            for row_index in range(min(len(df_raw), HEADER_SEARCH_ROWS)):
                row_values = df_raw.iloc[row_index].tolist()
                if ExcelConfig.SOURCE_HEADER.lower() in [
                    normalize_cell(cell) for cell in row_values
                ]:
                    header_row_index = row_index
                    header_row_values = row_values
                    break

            if header_row_index is None:
                print(f"Skipping: Header '{ExcelConfig.SOURCE_HEADER}' not found.")
                continue

            df = df_raw[header_row_index + 1 :].reset_index(drop=True)
            df.columns = header_row_values

            source_col_name = find_column(df.columns, ExcelConfig.SOURCE_HEADER)
            target_col_name = find_column(df.columns, ExcelConfig.TARGET_HEADER)
            speaker_col_name = find_column(df.columns, ExcelConfig.SPEAKER_HEADER)
            typemessage_col_name = find_column(
                df.columns, ExcelConfig.TYPEMESSAGE_HEADER
            )

            if target_col_name is None:
                print(f"Error: Target header '{ExcelConfig.TARGET_HEADER}' missing.")
                continue

            lines_to_translate_formatted = []
            original_row_indices_df = []
            row_types = []

            for index, row in df.iterrows():
                source_text = (
                    str(row[source_col_name]) if pd.notna(row[source_col_name]) else ""
                )
                existing_translation = (
                    str(row[target_col_name]) if pd.notna(row[target_col_name]) else ""
                )
                speaker_info = (
                    str(row[speaker_col_name])
                    if speaker_col_name and pd.notna(row[speaker_col_name])
                    else ""
                )
                message_type = (
                    str(row[typemessage_col_name]).strip().lower()
                    if typemessage_col_name and pd.notna(row[typemessage_col_name])
                    else ""
                )
                row_types.append(message_type)

                if source_text.strip() != "" and (
                    existing_translation.strip() == ""
                    or existing_translation.strip().startswith("TRANSLATION_ERROR")
                ):
                    if source_text in NAME_TERM_TRANSLATIONS:
                        lines_to_translate_formatted.append(
                            f"Line {index + 1}: {NAME_TERM_TRANSLATIONS[source_text]}"
                        )
                    else:
                        lines_to_translate_formatted.append(
                            LINE_FORMAT_TEMPLATE.format(
                                line_number=index + 1,
                                speaker=speaker_info if speaker_info else "Unknown",
                                text=source_text,
                            )
                        )
                    original_row_indices_df.append(index)

            translated_column_data = df[target_col_name].tolist()

            if lines_to_translate_formatted:
                character_styles_list_str = "\n".join(
                    f"- {name}: {style}"
                    for name, style in CHARACTER_SPEAKING_STYLES.items()
                )
                dict_translations = {}
                api_lines_formatted = []

                for formatted_line in lines_to_translate_formatted:
                    match = re.match(r"Line\s*(\d+)\s*:\s*(.*)", formatted_line)
                    if match:
                        dict_translations[int(match.group(1))] = match.group(2).strip()
                    else:
                        api_lines_formatted.append(formatted_line)

                translated_batch_text = ""
                parsed_api_translations = {}

                if api_lines_formatted:
                    batch_prompt = TRANSLATION_PROMPT_TEMPLATE.format(
                        source_lang=TranslatorConfig.SOURCE_LANGUAGE,
                        target_lang=TranslatorConfig.TARGET_LANGUAGE,
                        character_styles_list=character_styles_list_str
                        or "None provided.",
                        lines_to_translate="\n".join(api_lines_formatted),
                    )

                    print(f"Sending {len(api_lines_formatted)} lines to Gemini...")
                    translated_batch_text = translate_batch_with_gemini(batch_prompt)

                    if not translated_batch_text.startswith("BATCH_TRANSLATION_ERROR"):
                        translated_lines = re.findall(
                            r"Line\s*(\d+)\s*[:.]?\s*(.*?)(?=\nLine\s*\d+\s*[:.]?|\Z)",
                            translated_batch_text,
                            re.DOTALL,
                        )
                        parsed_api_translations = {
                            int(num): text.strip() for num, text in translated_lines
                        }

                for original_idx_df in original_row_indices_df:
                    prompt_line_number = original_idx_df + 1

                    if prompt_line_number in dict_translations:
                        translated_text = dict_translations[prompt_line_number]
                    elif translated_batch_text.startswith("BATCH_TRANSLATION_ERROR"):
                        translated_text = translated_batch_text
                    elif prompt_line_number in parsed_api_translations:
                        translated_text = parsed_api_translations[prompt_line_number]
                    else:
                        translated_text = (
                            f"PARSING_ERROR: Line {prompt_line_number} missing."
                        )

                    translated_column_data[original_idx_df] = wrap_translation(
                        translated_text,
                        file_name,
                        row_types[original_idx_df],
                    )

            df[target_col_name] = translated_column_data

            if source_file_path != output_file_path:
                shutil.copy2(source_file_path, output_file_path)

            try:
                workbook = openpyxl.load_workbook(output_file_path)
                sheet = workbook.active
                header_row_index_openpyxl = None
                target_col_index_openpyxl = None

                for row_index in range(1, min(sheet.max_row, HEADER_SEARCH_ROWS) + 1):
                    row_values = [
                        normalize_cell(cell.value) for cell in sheet[row_index]
                    ]
                    if ExcelConfig.TARGET_HEADER.lower() in row_values:
                        header_row_index_openpyxl = row_index - 1
                        target_col_index_openpyxl = row_values.index(
                            ExcelConfig.TARGET_HEADER.lower()
                        )
                        break

                if header_row_index_openpyxl is not None:
                    for df_index, translated_text in enumerate(translated_column_data):
                        excel_row_number = header_row_index_openpyxl + df_index + 2
                        cell = sheet.cell(
                            row=excel_row_number,
                            column=target_col_index_openpyxl + 1,
                        )
                        cell.value = translated_text

                    workbook.save(output_file_path)
                    print(f"Saved: {file_name}")
                    processed_count += 1
            except Exception as e:
                print(f"Error saving {file_name}: {e}")

        except ValueError as e:
            print(f"Error: {e}")

    return processed_count


# --- Run the script ---
if __name__ == "__main__":
    print("Starting Gemini Excel Batch Translator script...")
    total_processed = process_excel_files_in_folder()
    if total_processed > 0:
        print(f"\nScript finished. Processed {total_processed} files.")
