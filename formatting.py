# --- formatting.py ---
# This file contains functions related to text formatting and formatting configuration.

import textwrap # Import textwrap for handling text wrapping
import re # Import regex for potential post-processing

# --- Formatting Configuration ---
# Approximate maximum characters per line for general text wrapping.
# This is a fallback if specific rules don't apply.
# You will need to adjust this value based on your font, font size, and Excel settings.
DEFAULT_MAX_CHARS_PER_LINE = 40 # Example value - adjust as needed

# List of message types considered as dialogue for the maximum line break rule
DIALOGUE_TYPES = ["message", "messagelog"] # Add other types if needed

# Maximum number of line breaks allowed for dialogue types (excluding choice)
DEFAULT_MAX_DIALOGUE_LINE_BREAKS = 4

# Prefix for files requiring special "adv_pevent_" formatting rules
ADV_PEVENT_PREFIX = "adv_pevent_002_"

# Prefix for files where character-based wrapping should be skipped (adv_unit_)
ADV_UNIT_PREFIX = "adv_unit_"

# --- Formatting Rules for "adv_pevent_" files (Single Line/Bubble Choices) ---
# Approximate maximum characters per line for text in "adv_pevent_" files.
# This value is used as a fallback if per-line limits are not set.
ADV_PEVENT_MAX_CHARS = 29 # Adjust based on testing (approx. total half-width)

# Maximum number of line breaks allowed for "choice" type in "adv_pevent_" files.
ADV_PEVENT_MAX_CHOICE_BREAKS = 3

# *** IMPORTANT: Per-line character limits for "adv_pevent_" choices ***
# Set these values to the exact character limit for each line in the game's choice boxes.
# If set to None, the script will use ADV_PEVENT_MAX_CHARS as a single limit for wrapping.
# These limits are used as guides for the text content *excluding* the extra space before line breaks.
ADV_PEVENT_CHOICE_LINE1_CHARS = None # Example: 10
ADV_PEVENT_CHOICE_LINE2_CHARS = None # Example: 10
ADV_PEVENT_CHOICE_LINE3_CHARS = None # Example: 9


# --- Formatting Rules for other files (Bubble Choices only) ---
# Approximate maximum characters per line for text in other files.
# This value should aim to fit the bubble choice box (approx. 34 full-width / 43 half-width).
OTHER_MAX_CHARS = 43 # Adjust based on testing

# Maximum number of line breaks allowed for "choice" type in other files.
OTHER_MAX_CHOICE_BREAKS = 3


def wrap_text(text, file_name, message_type, default_max_chars, dialogue_types, default_max_dialogue_breaks, adv_pevent_prefix, adv_pevent_max_chars, adv_pevent_max_choice_breaks, other_max_chars, other_max_choice_breaks, adv_unit_prefix, adv_pevent_choice_line1_chars, adv_pevent_choice_line2_chars, adv_pevent_choice_line3_chars):
    """
    Applies various formatting rules to the translated text offline.
    Includes removing quotes, character conversions, wrapping, and line break limits.
    """
    if not text or not isinstance(text, str):
        return ""

    formatted_text = text.strip() # Start with stripped text

    # --- Apply Cleanup Rules (before wrapping) ---

    # Remove leading and trailing double quotes if present
    if formatted_text.startswith('"') and formatted_text.endswith('"'):
        formatted_text = formatted_text[1:-1]
    # Also handle triple double quotes that models sometimes output for multiline strings
    elif formatted_text.startswith('"""') and formatted_text.endswith('"""'):
         formatted_text = formatted_text[3:-3]

    # Convert various dash-like characters to ――
    formatted_text = formatted_text.replace('--', '――')
    formatted_text = formatted_text.replace('ーー', '――')
    formatted_text = formatted_text.replace('——', '――')
    formatted_text = formatted_text.replace('──', '――')
    # Added new dash character conversions
    formatted_text = formatted_text.replace('ー', '―')
    formatted_text = formatted_text.replace('—', '―')
    formatted_text = formatted_text.replace('─', '―')


    # Convert Japanese period (。) to standard period (.)
    formatted_text = formatted_text.replace('。', '.')

    # Convert Japanese ellipsis (…) to standard triple dot ellipsis (...)
    formatted_text = formatted_text.replace('…', '...')

    # Convert half-width tilde (~) to full-width tilde (～) as per prompt instructions
    formatted_text = formatted_text.replace('~', '～')


    # --- Rule 1: Remove trailing period for "choice" type (after initial cleanup) ---
    if message_type == "choice" and formatted_text.endswith('.'):
        formatted_text = formatted_text[:-1]
        # print(f"  Removed trailing period for choice: {formatted_text}") # Debugging


    # --- Determine wrapping parameters based on file name and message type ---
    max_chars_for_wrapping = default_max_chars # Default wrapping width
    max_breaks = None # No default max breaks unless it's a dialogue type

    is_adv_pevent_file = file_name.startswith(adv_pevent_prefix)
    is_adv_unit_file = file_name.startswith(adv_unit_prefix) # Check for adv_unit_ prefix

    # If it's an adv_unit_ file, skip character-based wrapping by setting max_chars_for_wrapping to infinity
    if is_adv_unit_file:
        max_chars_for_wrapping = float('inf')
        # print(f"  Skipping character wrapping for adv_unit_ file: {file_name}") # Debugging
    elif message_type == "choice":
        if is_adv_pevent_file:
            # Check if per-line limits are set for adv_pevent_ choices
            if adv_pevent_choice_line1_chars is not None and adv_pevent_choice_line2_chars is not None and adv_pevent_choice_line3_chars is not None:
                # Per-line limits are set, we will handle wrapping manually below, prioritizing words
                max_chars_for_wrapping = float('inf') # Disable textwrap.fill's width-based wrapping
                max_breaks = adv_pevent_max_choice_breaks
                # print(f"  Using per-line limits with word priority for adv_pevent_ choice: max_breaks={max_breaks}") # Debugging
            else:
                # Per-line limits not set, use the single ADV_PEVENT_MAX_CHARS for textwrap.fill
                max_chars_for_wrapping = adv_pevent_max_chars
                max_breaks = adv_pevent_max_choice_breaks
                # print(f"  Using single max_chars for adv_pevent_ choice (per-line limits not set): max_chars={max_chars_for_wrapping}, max_breaks={max_breaks}") # Debugging
        else:
            # Other files with choice type
            max_chars_for_wrapping = other_max_chars
            max_breaks = other_max_choice_breaks
            # print(f"  Applying other choice formatting: max_chars={max_chars_for_wrapping}, max_breaks={max_breaks}") # Debugging
    elif message_type in dialogue_types:
         # Apply default dialogue max breaks for non-choice dialogue types
         max_breaks = default_max_dialogue_breaks
         # print(f"  Applying default dialogue formatting: max_chars={max_chars_for_wrapping}") # Debugging
    # else:
         # No specific max breaks for other types (narration, etc.)
         # print(f"  Applying default formatting: max_chars={max_chars_for_wrapping}") # Debugging


    # --- Apply text wrapping ---
    # If per-line limits are set for adv_pevent_ choices, handle wrapping manually with word priority
    if is_adv_pevent_file and message_type == "choice" and adv_pevent_choice_line1_chars is not None and adv_pevent_choice_line2_chars is not None and adv_pevent_choice_line3_chars is not None:
        wrapped_lines = []
        remaining_text = formatted_text # Use the cleaned text
        line_limits = [adv_pevent_choice_line1_chars, adv_pevent_choice_line2_chars, adv_pevent_choice_line3_chars]

        words = remaining_text.split() # Split into words
        current_line_words = []

        for i, limit in enumerate(line_limits):
            if not words:
                break # No more words to process

            current_line_length = 0
            words_for_this_line = []

            for j, word in enumerate(words):
                word_length = len(word)
                # Add space length if it's not the very first word of the entire choice text
                # and not the first word of the current line
                space_length = 1 if words_for_this_line else 0

                if current_line_length + space_length + word_length <= limit:
                    # Word fits within the limit
                    words_for_this_line.append(word)
                    current_line_length += space_length + word_length
                else:
                    # Word exceeds the limit, break before this word
                    if words_for_this_line: # If there are words on the current line, add them
                        wrapped_lines.append(" ".join(words_for_this_line))
                        words = words[j:] # Remaining words start from the current word
                        break # Move to the next line limit
                    else:
                        # The first word itself exceeds the limit. Add the word and break.
                        wrapped_lines.append(word)
                        words = words[j+1:] # Remaining words start after this word
                        break # Move to the next line limit

            # If the inner loop finished without breaking (all remaining words fit in the last line)
            else:
                if words_for_this_line:
                    wrapped_lines.append(" ".join(words_for_this_line))
                words = [] # No remaining words


        # If there's still text after the third line (due to words exceeding the limit), add it as a fourth line
        if words:
             wrapped_lines.append(" ".join(words))


        # print(f"  Manual word-aware wrapping result (excluding space from limit): {wrapped_lines}") # Debugging)

    else:
        # Use textwrap.fill for other cases (including adv_pevent_ choices if per-line limits not set)
        # break_long_words=False prevents breaking words that are longer than max_chars_for_wrapping
        # replace_whitespace=False preserves existing whitespace like multiple spaces
        # If max_chars_for_wrapping is infinity, textwrap.fill will not wrap based on width
        wrapped_lines = textwrap.fill(formatted_text, width=max_chars_for_wrapping, break_long_words=False, replace_whitespace=False).splitlines()


    # --- Apply max line breaks if specified ---
    # This rule still applies even if character wrapping was skipped or done manually
    if max_breaks is not None and len(wrapped_lines) > max_breaks + 1: # +1 because splitlines doesn't count the last implicit line
        wrapped_lines = wrapped_lines[:max_breaks + 1] # Keep the first max_breaks + 1 lines
        # Optionally add an ellipsis or marker to indicate truncation
        # if not wrapped_lines[-1].endswith('...'):
        #     wrapped_lines[-1] += '...'
        # print(f"  Applied max breaks ({max_breaks}). Resulting lines: {len(wrapped_lines)}") # Debugging


    # --- Rule 2: Add extra space before line break for "choice" type ---
    # This rule now applies specifically to "choice" types, regardless of file prefix
    if message_type == "choice" and len(wrapped_lines) > 1:
        # Join lines with " \n" instead of "\n"
        final_text = " \n".join(wrapped_lines)
        # print(f"  Added extra space before line breaks for choice type: {final_text}") # Debugging)
    else:
        final_text = "\n".join(wrapped_lines)


    return final_text

# You can add other formatting functions here in the future
# def another_formatting_function(...):
#     pass
