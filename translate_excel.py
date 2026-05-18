import os
from google import genai
from google.genai import types
import pandas as pd
import time
import shutil
import re
import openpyxl

# --- Import Configuration ---
try:
    from config import (
        GEMINI_API_KEY, SOURCE_FOLDER_PATH, OUTPUT_FOLDER_PATH,
        TARGET_LANGUAGE, SOURCE_LANGUAGE, GEMINI_MODEL, TEMPERATURE,
        SOURCE_HEADER, TARGET_HEADER, SPEAKER_HEADER, TYPEMESSAGE_HEADER
    )
    print("Successfully imported configuration from config.py.")
except ImportError:
    print("Error: config.py not found or required variables not defined.")
    exit()


# --- Import Translation Dictionary ---
try:
    from dictionary import NAME_TERM_TRANSLATIONS
    print("Successfully imported NAME_TERM_TRANSLATIONS dictionary.")
except ImportError:
    print("Warning: dictionary.py not found. Proceeding without it.")
    NAME_TERM_TRANSLATIONS = {}

# --- Import Character Styles Dictionary ---
try:
    from character_styles import CHARACTER_SPEAKING_STYLES
    print("Successfully imported CHARACTER_SPEAKING_STYLES dictionary.")
except ImportError:
    print("Warning: character_styles.py not found. Proceeding without it.")
    CHARACTER_SPEAKING_STYLES = {}

# --- Import Prompt Templates ---
try:
    from prompts import TRANSLATION_PROMPT_TEMPLATE, LINE_FORMAT_TEMPLATE
    print("Successfully imported prompt templates from prompts.py.")
except ImportError:
    print("Error: prompts.py not found or templates not defined.")
    exit()

# --- Import Formatting Functions and Configuration ---
try:
    from formatting import (
        wrap_text,
        DEFAULT_MAX_CHARS_PER_LINE, DIALOGUE_TYPES, DEFAULT_MAX_DIALOGUE_LINE_BREAKS,
        ADV_PEVENT_PREFIX, ADV_PEVENT_MAX_CHARS, ADV_PEVENT_MAX_CHOICE_BREAKS,
        OTHER_MAX_CHARS, OTHER_MAX_CHOICE_BREAKS, ADV_UNIT_PREFIX,
        ADV_PEVENT_CHOICE_LINE1_CHARS, ADV_PEVENT_CHOICE_LINE2_CHARS, ADV_PEVENT_CHOICE_LINE3_CHARS
    )
    print("Successfully imported formatting functions.")
except ImportError:
    print("Error: formatting.py not found.")
    exit()


# --- API Setup ---
try:
    client = genai.Client(api_key=GEMINI_API_KEY)
    print(f"Gemini client initialized using model: {GEMINI_MODEL}")
except Exception as e:
    print(f"Error initializing Gemini client: {e}")
    exit()

def translate_batch_with_gemini(batch_prompt, model_name, temperature):
    """Calls the new Gemini API client with a single batch prompt."""
    if not batch_prompt or not isinstance(batch_prompt, str) or not batch_prompt.strip():
        return ""

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=batch_prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
            )
        )

        if response and response.text:
            return response.text.strip()
        
        return ""

    except Exception as e:
        print(f"Error translating batch: {e}")
        return f"BATCH_TRANSLATION_ERROR: {e}"


# --- Main Processing Logic ---

def process_excel_files_in_folder(source_folder_path, output_folder_path, gemini_model, api_key, source_lang, target_lang, temperature, source_header, target_header, speaker_header, typemessage_header, main_prompt_template, line_format_template, name_term_translations, character_speaking_styles, default_max_chars_per_line, dialogue_types, default_max_dialogue_breaks, adv_pevent_prefix, adv_pevent_max_chars, adv_pevent_max_choice_breaks, other_max_chars, other_max_choice_breaks, adv_unit_prefix, adv_pevent_choice_line1_chars, adv_pevent_choice_line2_chars, adv_pevent_choice_line3_chars):
    """Finds and processes Excel files (.xlsx) in a given local folder and saves to an output folder."""
    processed_count = 0
    
    if not os.path.isdir(source_folder_path):
        print(f"Error: Source folder not found at {source_folder_path}")
        return processed_count

    if not os.path.exists(output_folder_path):
        os.makedirs(output_folder_path)

    items = [f for f in os.listdir(source_folder_path) if f.endswith('.xlsx')]

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

            header_row_index_pandas = -1
            max_rows_to_search_pandas = min(len(df_raw), 10)
            header_row_values = None

            for i in range(max_rows_to_search_pandas):
                 current_row_values = df_raw.iloc[i].tolist()
                 current_row_str_values = [str(cell).strip().lower() for cell in current_row_values]

                 if source_header.lower() in current_row_str_values:
                      header_row_index_pandas = i
                      header_row_values = current_row_values
                      break

            if header_row_index_pandas == -1:
                print(f"Skipping: Header '{source_header}' not found.")
                continue

            df = df_raw[header_row_index_pandas + 1:].reset_index(drop=True)
            df.columns = header_row_values

            source_col_name = next((col for col in df.columns if str(col).strip().lower() == source_header.lower()), None)
            target_col_name = next((col for col in df.columns if str(col).strip().lower() == target_header.lower()), None)
            speaker_col_name = next((col for col in df.columns if str(col).strip().lower() == speaker_header.lower()), None)
            typemessage_col_name = next((col for col in df.columns if str(col).strip().lower() == typemessage_header.lower()), None)

            if target_col_name is None:
                 print(f"Error: Target header '{target_header}' missing.")
                 continue

            lines_to_translate_formatted = []
            source_texts = []
            original_row_indices_df = []
            row_types = []

            for index, row in df.iterrows():
                source_text = str(row[source_col_name]) if pd.notna(row[source_col_name]) else ""
                existing_translation = str(row[target_col_name]) if pd.notna(row[target_col_name]) else ""
                speaker_info = str(row[speaker_col_name]) if speaker_col_name and pd.notna(row[speaker_col_name]) else ""
                message_type = str(row[typemessage_col_name]).strip().lower() if typemessage_col_name and pd.notna(row[typemessage_col_name]) else ""
                row_types.append(message_type)

                if source_text.strip() != "" and (existing_translation.strip() == "" or existing_translation.strip().startswith("TRANSLATION_ERROR")):
                     if source_text in name_term_translations:
                         lines_to_translate_formatted.append(f"Line {index + 1}: {name_term_translations[source_text]}")
                         source_texts.append(source_text)
                         original_row_indices_df.append(index)
                     else:
                         formatted_line = line_format_template.format(
                             line_number=index + 1,
                             speaker=speaker_info if speaker_info else "Unknown",
                             text=source_text
                         )
                         lines_to_translate_formatted.append(formatted_line)
                         source_texts.append(source_text)
                         original_row_indices_df.append(index)

            translated_column_data = df[target_col_name].tolist()

            if lines_to_translate_formatted:
                 character_styles_list_str = "\n".join([f"- {name}: {style}" for name, style in character_speaking_styles.items()])
                 dict_translations = {}
                 api_lines_formatted = []

                 for formatted_line in lines_to_translate_formatted:
                     match = re.match(r'Line\s*(\d+)\s*:\s*(.*)', formatted_line)
                     if match:
                         line_num = int(match.group(1))
                         translation = match.group(2).strip()
                         dict_translations[line_num] = translation
                     else:
                         api_lines_formatted.append(formatted_line)

                 translated_batch_text = ""
                 parsed_api_translations = {}
                 
                 if api_lines_formatted:
                     batch_prompt = main_prompt_template.format(
                         source_lang=source_lang,
                         target_lang=target_lang,
                         character_styles_list=character_styles_list_str or "None provided.",
                         lines_to_translate="\n".join(api_lines_formatted)
                     )

                     print(f"Sending {len(api_lines_formatted)} lines to Gemini...")
                     translated_batch_text = translate_batch_with_gemini(batch_prompt, gemini_model, temperature)
                     
                     if not translated_batch_text.startswith("BATCH_TRANSLATION_ERROR"):
                         translated_lines = re.findall(r'Line\s*(\d+)\s*[:.]?\s*(.*?)(?=\nLine\s*\d+\s*[:.]?|\Z)', translated_batch_text, re.DOTALL)
                         parsed_api_translations = {int(num): text.strip() for num, text in translated_lines}

                 for original_idx_df in original_row_indices_df:
                      prompt_line_number = original_idx_df + 1
                      translated_text = ""
                      if prompt_line_number in dict_translations:
                           translated_text = dict_translations[prompt_line_number]
                      elif translated_batch_text.startswith("BATCH_TRANSLATION_ERROR"):
                           translated_text = translated_batch_text
                      elif prompt_line_number in parsed_api_translations:
                           translated_text = parsed_api_translations[prompt_line_number]
                      else:
                           translated_text = f"PARSING_ERROR: Line {prompt_line_number} missing."

                      row_type = row_types[original_idx_df]
                      translated_text = wrap_text(
                          translated_text, file_name, row_type,
                          default_max_chars_per_line, dialogue_types,
                          default_max_dialogue_breaks, adv_pevent_prefix,
                          adv_pevent_max_chars, adv_pevent_max_choice_breaks,
                          other_max_chars, other_max_choice_breaks, adv_unit_prefix,
                          adv_pevent_choice_line1_chars, adv_pevent_choice_line2_chars, adv_pevent_choice_line3_chars
                      )
                      translated_column_data[original_idx_df] = translated_text

            df[target_col_name] = translated_column_data

            if source_file_path != output_file_path:
                 shutil.copy2(source_file_path, output_file_path)

            try:
                workbook = openpyxl.load_workbook(output_file_path)
                sheet = workbook.active
                header_row_index_openpyxl = -1
                target_col_index_openpyxl = -1

                for r_idx in range(1, min(sheet.max_row, 10) + 1):
                     row_values = [str(cell.value).strip().lower() if cell.value else "" for cell in sheet[r_idx]]
                     if target_header.lower() in row_values:
                          header_row_index_openpyxl = r_idx - 1
                          target_col_index_openpyxl = row_values.index(target_header.lower())
                          break

                if header_row_index_openpyxl != -1:
                    for df_index in range(len(df)):
                         excel_row_number = header_row_index_openpyxl + df_index + 2
                         cell = sheet.cell(row=excel_row_number, column=target_col_index_openpyxl + 1)
                         cell.value = translated_column_data[df_index]
                    workbook.save(output_file_path)
                    print(f"Saved: {file_name}")
                    processed_count += 1
            except Exception as e:
                 print(f"Error saving {file_name}: {e}")

        except Exception as e:
            print(f"Unexpected error in {file_name}: {e}")

    return processed_count

# --- Run the script ---
if __name__ == '__main__':
    print("Starting Gemini Excel Batch Translator script...")
    total_processed = process_excel_files_in_folder(
        SOURCE_FOLDER_PATH,
        OUTPUT_FOLDER_PATH,
        GEMINI_MODEL,  # Fixed: changed lowercase 'gemini_model' to uppercase 'GEMINI_MODEL'
        GEMINI_API_KEY,
        SOURCE_LANGUAGE,
        TARGET_LANGUAGE,
        TEMPERATURE,
        SOURCE_HEADER,
        TARGET_HEADER,
        SPEAKER_HEADER,
        TYPEMESSAGE_HEADER,
        TRANSLATION_PROMPT_TEMPLATE,
        LINE_FORMAT_TEMPLATE,
        NAME_TERM_TRANSLATIONS,
        CHARACTER_SPEAKING_STYLES,
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
        ADV_PEVENT_CHOICE_LINE3_CHARS
    )
    print(f"\nScript finished. Processed {total_processed} files.")