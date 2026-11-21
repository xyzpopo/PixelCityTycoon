"""Small Hangul composition helpers for the on-screen two-set keyboard."""

INITIALS = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
VOWELS = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
FINALS = " ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"

INITIAL_INDEX = {value: index for index, value in enumerate(INITIALS)}
VOWEL_INDEX = {value: index for index, value in enumerate(VOWELS)}
FINAL_INDEX = {value: index for index, value in enumerate(FINALS) if value}

COMBINE_VOWEL = {
    ("ㅗ", "ㅏ"): "ㅘ", ("ㅗ", "ㅐ"): "ㅙ", ("ㅗ", "ㅣ"): "ㅚ",
    ("ㅜ", "ㅓ"): "ㅝ", ("ㅜ", "ㅔ"): "ㅞ", ("ㅜ", "ㅣ"): "ㅟ",
    ("ㅡ", "ㅣ"): "ㅢ",
}
SPLIT_VOWEL = {value: pair[0] for pair, value in COMBINE_VOWEL.items()}
COMBINE_FINAL = {
    ("ㄱ", "ㅅ"): "ㄳ",
    ("ㄴ", "ㅈ"): "ㄵ", ("ㄴ", "ㅎ"): "ㄶ",
    ("ㄹ", "ㄱ"): "ㄺ", ("ㄹ", "ㅁ"): "ㄻ", ("ㄹ", "ㅂ"): "ㄼ",
    ("ㄹ", "ㅅ"): "ㄽ", ("ㄹ", "ㅌ"): "ㄾ", ("ㄹ", "ㅍ"): "ㄿ",
    ("ㄹ", "ㅎ"): "ㅀ", ("ㅂ", "ㅅ"): "ㅄ",
}
SPLIT_FINAL = {value: pair for pair, value in COMBINE_FINAL.items()}
DOUBLE_INITIAL = {
    ("ㄱ", "ㄱ"): "ㄲ", ("ㄷ", "ㄷ"): "ㄸ", ("ㅂ", "ㅂ"): "ㅃ",
    ("ㅅ", "ㅅ"): "ㅆ", ("ㅈ", "ㅈ"): "ㅉ",
}
SPLIT_INITIAL = {value: pair[0] for pair, value in DOUBLE_INITIAL.items()}

# A final consonant that moves to the next syllable when a vowel is typed.
FINAL_TO_INITIAL = {value: value for value in INITIAL_INDEX}
FINAL_TO_INITIAL.update({
    "ㄳ": "ㅅ", "ㄵ": "ㅈ", "ㄶ": "ㅎ", "ㄺ": "ㄱ", "ㄻ": "ㅁ",
    "ㄼ": "ㅂ", "ㄽ": "ㅅ", "ㄾ": "ㅌ", "ㄿ": "ㅍ", "ㅀ": "ㅎ",
    "ㅄ": "ㅅ",
})


def _make_syllable(initial: str, vowel: str, final: str = "") -> str:
    return chr(0xAC00 + (INITIAL_INDEX[initial] * 21 + VOWEL_INDEX[vowel]) * 28
               + FINAL_INDEX.get(final, 0))


def _split_syllable(char: str):
    code = ord(char) - 0xAC00
    if not 0 <= code < 11172:
        return None
    initial = INITIALS[code // 588]
    vowel = VOWELS[(code % 588) // 28]
    final_index = code % 28
    final = FINALS[final_index] if final_index else ""
    return initial, vowel, final


def append_hangul_jamo(text: str, jamo: str) -> str:
    """Append a compatibility jamo and compose a basic Korean syllable."""
    if jamo in VOWEL_INDEX:
        if text:
            last = text[-1]
            parts = _split_syllable(last)
            if parts:
                initial, vowel, final = parts
                if not final:
                    combined = COMBINE_VOWEL.get((vowel, jamo))
                    if combined:
                        return text[:-1] + _make_syllable(initial, combined)
                else:
                    split = SPLIT_FINAL.get(final)
                    if split:
                        keep_final, moving_final = split
                    else:
                        keep_final, moving_final = "", final
                    moving_initial = FINAL_TO_INITIAL.get(moving_final)
                    if moving_initial in INITIAL_INDEX:
                        previous = _make_syllable(initial, vowel, keep_final)
                        return text[:-1] + previous + _make_syllable(moving_initial, jamo)

            if last in INITIAL_INDEX:
                return text[:-1] + _make_syllable(last, jamo)
            if last in VOWEL_INDEX:
                combined = COMBINE_VOWEL.get((last, jamo))
                if combined:
                    return text[:-1] + combined
        return text + jamo

    if jamo in INITIAL_INDEX:
        if text:
            last = text[-1]
            parts = _split_syllable(last)
            if parts:
                initial, vowel, final = parts
                if not final and jamo in FINAL_INDEX:
                    return text[:-1] + _make_syllable(initial, vowel, jamo)
                combined = COMBINE_FINAL.get((final, jamo)) if final else None
                if combined:
                    return text[:-1] + _make_syllable(initial, vowel, combined)
            if last in INITIAL_INDEX:
                combined_initial = DOUBLE_INITIAL.get((last, jamo))
                if combined_initial:
                    return text[:-1] + combined_initial
        return text + jamo

    return text + jamo


def backspace_hangul(text: str) -> str:
    """Remove one composing step, preserving the earlier part of a syllable."""
    if not text:
        return text
    last = text[-1]
    parts = _split_syllable(last)
    if parts:
        initial, vowel, final = parts
        if final:
            split = SPLIT_FINAL.get(final)
            return text[:-1] + _make_syllable(
                initial, vowel, split[0] if split else ""
            )
        if vowel in SPLIT_VOWEL:
            return text[:-1] + _make_syllable(initial, SPLIT_VOWEL[vowel])
        return text[:-1] + initial
    if last in SPLIT_INITIAL:
        return text[:-1] + SPLIT_INITIAL[last]
    return text[:-1]
