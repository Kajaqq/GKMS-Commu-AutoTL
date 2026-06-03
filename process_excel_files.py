from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.cell.cell import Cell, MergedCell
from tqdm import tqdm

# --- Import Configuration ---
from ai.Models import PromptReferences, SourceLine, TranslationPrompt, InvalidHeaderException
from ai.translator import GeminiTranslationClient
from config.config import ExcelConfig, TranslatorConfig
from config.dictionary import NAME_TERM_TRANSLATIONS
from utils.text_utils import normalize_cell, safe_str, strip_whitespace
from utils.formatting import wrap_text
from utils.translator_helper import get_prompt_references, parse_translation_response

# --- Sheet utils ---
expected_header = [
    ExcelConfig.TYPE,
    ExcelConfig.ORIGINAL_SPEAKER,
    ExcelConfig.TRANSLATED_SPEAKER,
    ExcelConfig.SOURCE,
    ExcelConfig.TARGET,
]
filled_rows = len(expected_header)

def validate_header_row(sheet):
    """
    Checks if the header row is present and contains the expected headers
    """
    sheet_header = [normalize_cell(cell.value) for cell in sheet[1]]
    sheet_header = sheet_header[:filled_rows]
    if sheet_header != expected_header:
        raise InvalidHeaderException(
                f"Header row has incorrect headers: "
                f"Expected headers: {', '.join(expected_header)}."
                f"File headers: {', '.join(sheet_header)}"
        )

def load_workbook(source_file: Path) -> tuple[openpyxl.Workbook, Any]:
    workbook = openpyxl.load_workbook(source_file)
    sheet = workbook.active
    if sheet:
        return workbook, sheet
    else:
        raise RuntimeError("Workbook is empty. Skipping.")

# --- API Calling ---

def request_translations_from_api(
    source_lines: list[SourceLine],
    references: PromptReferences,
    translation_client: GeminiTranslationClient,
) -> dict[int, str]:
    """
    Builds the prompt, calls the Gemini API, and parses the response.

    Returns parsed translations keyed by workbook line number.
    """
    batch_prompt = TranslationPrompt(
        references=references,
        lines=source_lines,
        source_lang=TranslatorConfig.SOURCE_LANGUAGE,
        target_lang=TranslatorConfig.TARGET_LANGUAGE,
    )
    api_lines_numbers = {line.line_number for line in source_lines}
    print(f"Sending {len(source_lines)} lines to Gemini...")
    api_translations = translation_client.translate_batch(batch_prompt)

    return parse_translation_response(
        api_translations,
        api_lines_numbers,
    )

# --- Main Processing Logic  ---

@dataclass(slots=True)
class WorkbookTranslator:
    """
    Processes a single Excel workbook: reads, translates, and saves.
    Workflow:
    process -> collect_rows -> translate_rows -> write_translations -> save
    """
    source_file: Path
    output_file: Path
    translation_client: GeminiTranslationClient | None = None
    replace_single_term: bool = False

    # Internal variables
    workbook: openpyxl.Workbook = field(init=False)
    sheet: Any = field(init=False)
    source_lines: list[SourceLine] = field(default_factory=list, init=False) # Formatted lines for translation -- {line_num, speaker, text} format
    dict_translations: dict[int, str] = field(default_factory=dict, init=False) # For `replace_from_dict` usage
    row_metadata: list[tuple[int, Cell, str]] = field(default_factory=list, init=False) # Metadata of rows that need translation

    @property
    def file_name(self) -> str:
        return self.source_file.name

    def process(self) -> bool:
        """
        Orchestrates the translation process
        """
        self.workbook, self.sheet = load_workbook(self.source_file)
        validate_header_row(self.sheet) # If this fails, the rest doesn't continue
        self.collect_rows()

        if not self.row_metadata:
            print(f"No translations needed for {self.file_name}")
            return self.save(overwrite=False)

        parsed_api_translations = self.translate_rows()
        translation_error_count = self.write_translations(parsed_api_translations)
        saved = self.save()

        if translation_error_count > 0:
            # TODO: Expand this to allow choosing from:
            #  a) erroring out(strict mode)
            #  b) retrying with the full context,
            #  c) retrying with only the failed lines
            #  d) Doing nothing (Warning only, current behaviour)
            print(f"WARNING: {self.file_name} may require a rerun due to {translation_error_count} translation errors.")

        return saved

    def collect_rows(self) -> None:
        # All rows, excluding header
        data_rows = self.sheet.iter_rows(min_row=2, min_col=1, max_col=filled_rows)

        # Read and rows and prepare the data
        for line_number, row in enumerate(data_rows, start=1):
            message_type_cell, origin_speaker_cell, speaker_cell, source_cell, target_cell = row

            # Check if the translation cell is not a MergedCell
            if isinstance(target_cell, MergedCell):
                print(f"WARNING: A merged translation cell was found in row {line_number + 1}")
                print("These can not be wrapped nor written properly, skipping row.")
                continue

            # Converts None to empty string and strips leading whitespace
            source_text = safe_str(source_cell.value)
            translation_cell = safe_str(target_cell.value)
            speaker_info = safe_str(speaker_cell.value)
            origin_speaker_info = safe_str(origin_speaker_cell.value)
            message_type = safe_str(message_type_cell.value).lower()
            speaker = speaker_info or origin_speaker_info

            # Check if translation is required
            # Assume that if there's source_text and existing translation is empty
            # or starts with "TRANSLATION_ERROR", it needs translation

            needs_translation = source_text != "" and (
                translation_cell == "" or translation_cell.startswith("TRANSLATION_ERROR")
            )
            if not needs_translation:
                continue

            # Dict translation for exact line matches - see Config for more info on this
            if self.replace_single_term:
                normalized_source_text = strip_whitespace(source_text)
                if normalized_source_text in NAME_TERM_TRANSLATIONS:
                    self.dict_translations[line_number] = NAME_TERM_TRANSLATIONS[normalized_source_text]
                    self.row_metadata.append((line_number, target_cell, message_type))
                    continue

            # Save metadata of rows that will be translated
            self.source_lines.append(SourceLine(line_number=line_number, speaker=speaker, text=source_text))
            self.row_metadata.append((line_number, target_cell, message_type))

    def translate_rows(self) -> dict[int, str]:
        if not self.source_lines:
            return {}

        translation_client = self.translation_client or GeminiTranslationClient()
        translation_references = get_prompt_references(self.source_lines)

        return request_translations_from_api(
            source_lines=self.source_lines,
            references=translation_references,
            translation_client=translation_client,
        )

    def write_translations(self, parsed_api_translations: dict[int, str]) -> int:
        translation_error_count = 0

        for line_number, target_cell, message_type in self.row_metadata:
            if self.replace_single_term and line_number in self.dict_translations:
                translated_text = self.dict_translations[line_number]
            elif line_number in parsed_api_translations:
                translated_text = parsed_api_translations[line_number]
            else:
                translated_text = "TRANSLATION_ERROR: Something happened. You shouldn't be seeing this."

            if translated_text.startswith("TRANSLATION_ERROR"):
                translation_error_count += 1

            # TODO: Verify the formatting logic
            target_cell.value = wrap_text(translated_text, self.file_name, message_type)

        return translation_error_count

    def save(self, *, overwrite: bool = True) -> bool:
        if self.output_file.exists() and not overwrite:
            print("\nExisting file was not modified.")
            return False

        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self.workbook.save(self.output_file)
        print(f"Saved output to: {self.output_file}")
        return True

# --- Parallel Folder Processing ---

def process_excel_files_in_folder(
    source_folder_path=TranslatorConfig.SOURCE_FOLDER_PATH,
    output_folder_path=TranslatorConfig.OUTPUT_FOLDER_PATH,
    max_parallel_files=TranslatorConfig.MAX_PARALLEL_FILES,
    replace_single_term=TranslatorConfig.REPLACE_SINGLE_TERM,
):
    """
    Finds and processes Excel files (.xlsx) in a given local folder.
    """
    processed_count = 0
    is_single_file = False
    source_folder = Path(source_folder_path)
    output_folder = Path(output_folder_path)

    if not source_folder.is_dir():
        raise NotADirectoryError(f"Source folder not found at {source_folder}")

    output_folder.mkdir(parents=True, exist_ok=True)

    commu_files = sorted(source_folder.glob("*.xlsx"))
    if commu_files:
        commu_len = len(commu_files)
        if commu_len > 1:
            print(f"Found {commu_len} Excel files in {source_folder}.")
            print(f"Will run {max_parallel_files} in parallel.")
        elif commu_len == 1:
            print(f"Found one Excel file in {source_folder}.")
            print("Running in single file mode.")
            is_single_file = True
    else:
        raise FileNotFoundError(f"No Excel files found in {source_folder}.")

    translation_client = GeminiTranslationClient()

    def process_file(source_file_path: Path) -> bool:
        source_file_name = source_file_path.name
        output_file_path = output_folder / source_file_name
        translator = WorkbookTranslator(source_file=source_file_path,
                                        output_file=output_file_path,
                                        translation_client=translation_client,
                                        replace_single_term=replace_single_term)
        print(f"\n--- Processing file: {source_file_name} ---")
        print("This may take a while, please be patient.")
        return translator.process()

    worker_count = max(1, max_parallel_files)

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(process_file, source_file_path): source_file_path for source_file_path in commu_files
        }
        for future in tqdm(as_completed(futures),total=len(futures), desc="Translating files",  unit="file", disable=is_single_file):
            source_file_path = futures[future]
            try:
                if future.result():
                    processed_count += 1
            except Exception as e:
                print(f"Error processing {source_file_path.name}: {e}")

    return processed_count


# --- Run the script ---
if __name__ == "__main__":
    print("Starting Gakumas Commu Excel Batch Translator script...")
    total_processed = process_excel_files_in_folder()
    if total_processed > 0:
        print(f"\nScript finished. Processed {total_processed} files.")
