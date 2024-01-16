import re
import unicodedata

# List of lists `[start character, end character of parenthesis]`.
# Used by `tear_paren_contents()`.
PARENS = [['(',')'], ['—','—'], ['–','–']]

##### Regular expressions ######################################################
HIRAGANA_REGEX = r'[\u3040-\u309F]'
KATAKANA_REGEX = r'[\u30A0-\u30FF]'
HALFKANA_REGEX = r'[\uFF61-\uFF9F]'  # Match for halfwidth katakana
# Match for hiragana, katakana, and halfwidth katakana
KANA_REGEX = r'[\u3040-\u309F\u30A0-\u30FF\uFF61-\uFF9F]'
KANJI_REGEX = r'[々〇〻\u3400-\u9FFF\uF900-\uFAFF]|[\uD840-\uD87F][\uDC00-\uDFFF]'
HALFWIDTH_REGEX = r'[\x01-\x7E\xA1-\xDF]'
HALFWIDTH_REPTN = re.compile(HALFWIDTH_REGEX)  # Used by `tear_paren_contents()`
FULLWIDTH_REGEX = r'[^\x01-\x7E\xA1-\xDF]'

# Serial width-different characters. Used by `space_width_gap()`.
HALF_AND_FULLWIDTH_REPTN = re.compile(f'({HALFWIDTH_REGEX})({FULLWIDTH_REGEX})')
FULL_AND_HALFWIDTH_REPTN = re.compile(f'({FULLWIDTH_REGEX})({HALFWIDTH_REGEX})')

# Used by `join_chunks()`
SPACE_BETWEEN_FULLWIDTH_REPTN = re.compile(
    f'({FULLWIDTH_REGEX}) ({FULLWIDTH_REGEX})'
)
# Default pattern of sentence separators
SENTENCE_SEP_REGEX = r'[\r\n\?!。]'
# Used by `clean_split_text()`
SENTENCE_SEP_REPTN = re.compile(SENTENCE_SEP_REGEX)

# patterns of strings that cannot be split anymore. Used by `chunk_and_split()`.
UNSPLITTABLE_CHUNKS = [f'^{HALFWIDTH_REGEX}+$', f'^{SENTENCE_SEP_REGEX}+$']

# Used by `remove_extra_whitespaces()`
MULTI_WHITESPACES_REPTNS = [re.compile(f"({i})" + "{2,}") for i in [
    " ", r"\r\n", r"\r", r"\n", r"\t"
]]

# Default pattern of strings in parentheses to be discarded in text cleaning.
# Used by `tear_paren_contents()`.
INVALID_PAREN_CONTENTS = [re.compile(i) for i in [
    '^$',
    r'^\s+$',
    r'^\w{1,5}$',
    f'^( |・|{HIRAGANA_REGEX})+$',
    f'^( |・|{KATAKANA_REGEX})+$',
    f'^( |・|{HALFKANA_REGEX})+$',
    f'^( |・|{KANJI_REGEX})+$'
]]

# Default pattern of valid sentences.
# Match for strings that has more than 5 characters (halfwidth numbers,
# halfwidth alphabets, Kana, or Kanji).
SENTENCE_REGEX = f"^([ '\\da-z]|{KANA_REGEX}|{KANJI_REGEX})" + "{5,}$"
SENTENCE_REPTN = re.compile(SENTENCE_REGEX)  # Used by `clean_split_text()`

# List of lists as an instruction for string replaceing.
# Used by `clean_split_text()`.
# `[[original pattern, replaced pattern], ...]`
# String will be replaced in order of this list.
CLEAN_TEXT_SUBS = [[re.compile(i[0]), i[1]] for i in [
    # Remove HTML tags
    [r"<(\"[^\"]*\"|'[^']*'|[^'\">])*>", ""],
    # Remove editor's notes.
    # E.g. "(...)", "(注1)", "〔中略〕", "[略]", "(原文ママ)"
    [r'[\[\(〔](\.+|[注註]? *\d+|[中省]?略|ママ|原文ママ)[\]\)〕]', ''],
    # Unify single quotes. E.g. "I’m", "dancin’", "‘foobar’"
    ['’', "'"],
    # Mask all numbers with 0. E.g. "012", "0.1", "0,1", "0'1", "0・1", "1/2"
    [r'\d+', '0'],
    [r"0[\.,'・0/]*0[\.,'・0/]*", '0'],
    # Remove periods in abbreviation terms. E.g. "r.i.p." -> "rip."
    [r'([a-z])\.([a-z])', r'\1\2'],
    # Remove brackets
    [r'[「」『』‘"“”]', ''],
    # Blank some characters
    [r'[\.,、\-~・/]', ' '],

    # Remove ruby transcriptions (parentheses style)
    # E.g. "脆弱(ぜいじゃく)", "resilience (レジリエンス)"
    # [f'([a-z]|{KANJI_REGEX}) *\\(( |{KANA_REGEX})+\\)', r'\1'],

    # Remove ruby transcriptions (Aozora Bunko style).
    # E.g. "脆弱《ぜいじゃく》", "resilience《レジリエンス》"
    [f'([a-z]|{KANJI_REGEX}) *《( |{KANA_REGEX})+》', r'\1'],

    # Remove ruby transcriptions (LaTeX style).
    # E.g. "{脆弱|ぜいじゃく}", "{resilience|レジリエンス}"
    [r'\{' + f'([a-z]|{KANJI_REGEX})\\|( |{KANA_REGEX})+' + r'\}', r'\1'],

    # Remove en/em dashes at the end of sentences/last index. E.g. "hoge—"
    ['[–—]+ *(' + SENTENCE_SEP_REGEX + '|$)', r'\1'],
    # Remove en/em dashes at the top of sentences/first index. E.g. "—hoge"
    ['(' + SENTENCE_SEP_REGEX + '|^) *[–—]+', r'\1']
]]
################################################################################

##### Consts for syntax check ##################################################
NEGATIVE_REPTNS = [re.compile(f" {i} ") for i in [
    "[な無](く|い|き|けれ|かっ|)",
    "[ずぬん]",
    "ざ[りれ]",
    "(まい|だめ|ダメ|駄目|いや|イヤ|嫌|むり|ムリ|無理)",
]]
INTERROG_REPTNS = [re.compile(f" {i} ") for i in ["[かの]", "だろう"]]
HYPOTH_REPTNS = [re.compile(f" {i} ") for i in ["[ばも]", "(なら|たら|でも)"]]
FIGURATIVE_REPTNS = [re.compile(f" {i} ") for i in [
    "よう", "様", "みた[いく]", "(ごと|如)[くき]"
]]
DESID_REPTNS = [re.compile(f" {i} ") for i in [
    "[ほ欲]しい", "た[いく]", "(くだ|下)さい", "よう", "様"
]]
# cooccurrence
CO_EXPS = [[re.compile(f" {i[0]} "), i[1]] for i in [
    ["(いく|幾)ら", HYPOTH_REPTNS + INTERROG_REPTNS],
    ["[も若](し|し も)", HYPOTH_REPTNS],
    ["(かり|仮|假)に", HYPOTH_REPTNS],
     # "た と え" is workaround for Unidic.
    ["(たと|た と |例)え", HYPOTH_REPTNS],
    ["(どん|何ん?)な", HYPOTH_REPTNS + INTERROG_REPTNS],
    ["(な ん|なん|なに|何)", HYPOTH_REPTNS + INTERROG_REPTNS],
    ["どの", HYPOTH_REPTNS + INTERROG_REPTNS],
    ["まさ か", ["ね", "なんて"]],
    ["まさか", NEGATIVE_REPTNS],
    ["(全然|ぜんぜん|zen zen)", NEGATIVE_REPTNS],
    ["(まった|全)く", NEGATIVE_REPTNS],
    ["(なに|なん|何) も", NEGATIVE_REPTNS],
    ["(決|けっ)して", NEGATIVE_REPTNS],
    ["ちっとも", NEGATIVE_REPTNS],
    ["(少|すこ)しも", NEGATIVE_REPTNS],
    ["(あん?ま|余|餘)り", NEGATIVE_REPTNS],
    ["さほど", NEGATIVE_REPTNS],
    ["(たい|大)して", NEGATIVE_REPTNS],
    ["(めった|滅多) に", NEGATIVE_REPTNS],
    ["(かなら|必)ず しも", NEGATIVE_REPTNS],
    ["(とうてい|到底)", NEGATIVE_REPTNS],
    ["(いま|未)だ", NEGATIVE_REPTNS],
    ["(なぜ|何故)", INTERROG_REPTNS],
    ["(いったい|一体)", INTERROG_REPTNS],
    ["[は果]たして", INTERROG_REPTNS],
    ["どう .+ (たら|ば)", INTERROG_REPTNS],
    ["どう し て [^も].*", INTERROG_REPTNS],
    # ["(な ん|何) で [^も].*", INTERROG_REPTNS],
    # ["(なに|なん|何) が", INTERROG_REPTNS],
    ["(いつ|何時) .*[^もか].*", INTERROG_REPTNS],
    ["(いかが|如何)", INTERROG_REPTNS],
    ["(いか|如何)に [^も].*", INTERROG_REPTNS],
    ["まるで", FIGURATIVE_REPTNS],
    ["あたかも", FIGURATIVE_REPTNS],
    ["どう やら", FIGURATIVE_REPTNS],
    ["(ぜひ|是非)", DESID_REPTNS],
    ["どう(ぞ| か)", DESID_REPTNS],
    ["どう", INTERROG_REPTNS],
    ["(いつ|何時) か", DESID_REPTNS + HYPOTH_REPTNS],
]]
################################################################################

def space_width_gap(text: str):
    """ Inserts a space between halfwidth and fullwidth characters.

    Example:
        ```
        >>> space_width_gap("ほげfooほげ012")
        "ほげ foo ほげ 012"
        ```
    """
    text = HALF_AND_FULLWIDTH_REPTN.sub(r'\1 \2', text)
    text = FULL_AND_HALFWIDTH_REPTN.sub(r'\1 \2', text)
    return text

def join_chunks(chunks: list):
    """ Joins strings in `chunks` into one string.

    Strings are combined on a space-by-space basis, and spaces between
    consecutive fullwidth characters are removed.

    Example:
        ```
        >>> join_chunks(["ほげ", "ふが", "foo", "bar"])
        "ほげふが foo bar"
        >>> join_chunks(["ほげ ふが", "foo bar"])
        "ほげふが foo bar"
        ```
    """
    text = ' '.join(chunks)

    while True:
        s = SPACE_BETWEEN_FULLWIDTH_REPTN.subn(r'\1\2', text)
        if s[1] == 0:
            break
        text = s[0]

    return text

def chunk_and_split(
    splitter, text: str,
    no_split_patterns: list[str | re.Pattern] = UNSPLITTABLE_CHUNKS,
    **kwargs
):
    """ Sprits `text` by spaces, and further breaks them up with the given
    callback function `splitter`.

    Args:
        splitter (function): Callback function that splits string into some
                             units (e.g. words).
        no_split_patterns: Regular expressions representing a string pattern
                           that is not passed to `splitter`.

    Return:
        list: List of split strings.

    Example:
        ```
        >>> text = "吾輩は tomcat である 24h"
        >>> # Example function that splits a text into morphems
        >>> splitter_function(text)
        ["吾輩", "は", "tom", "cat", "で", "ある", "24", "h"]
        >>> chunk_and_split(splitter_function, text, r"^[\da-zA-Z]+$")
        ["吾輩", "は", "tomcat", "で", "ある", "24h"]
        ```
    """
    no_split_reptns = [i if type(i) is re.Pattern else re.compile(i)
                       for i in no_split_patterns]

    chunks = text.split(' ')
    ret = []
    for chunk in chunks:
        if chunk == '':
            continue

        for r in no_split_reptns:
            if r.search(chunk):
                ret.append(chunk)
                break
        else:
            ret.extend(splitter(chunk))

    return ret

def remove_extra_whitespaces(text:str):
    for i in MULTI_WHITESPACES_REPTNS:
        text = i.sub(r"\1", text)
    return text

def tear_paren_contents(
    text: str, parens: list[list[str, str]] = PARENS,
    invalid_contents: list[str | re.Pattern] = INVALID_PAREN_CONTENTS
):
    """ Tears parenthetical parts away from the text,

    Args:
        text: String that possibly contains parentheses.
        parens: List of lists `[start character, end character of parenthesis]`.
        invalid_contents: List of regular expressions that describe patterns of
                          contents in parentheses to be excluded from the return
                          list.

    Return:
        list [str]: List of strings. The first element is `text` without
                    parentheses (both their symbols and contents). Others are
                    contents in parentheses.

    Example:
        ```
        >>> text = "ほげ (12) ふが<注>foo(bar)baz"
        >>> parens = [["(", ")"], ["<", ">"]]
        >>> invalid_contents = ["^\d+$", "^注$"]
        >>> tear_paren_contents(text, parens, invalid_contents)
        ["ほげふがfoo baz", "bar"]
        ```
    """
    invalid_content_reptns = [i if type(i) is re.Pattern else re.compile(i)
                              for i in invalid_contents]

    ret = []
    for paren in parens:
        start = re.escape(paren[0])
        end = re.escape(paren[1])
        while True:
            found_parens = [
                {
                    'span': i.span(),
                    'pattern': re.escape(i.group()),
                    'content': i.group(1)
                }
                for i in re.finditer(f' *{start}([^{start}{end}]+){end} *',
                                     text)
                ]
            if found_parens == []:
                break

            # List to be used when remove/replace parens in `text`.
            subs = []
            for p in found_parens:
                pre_halfwidth = HALFWIDTH_REPTN.match(
                    text[p['span'][0] - 1 : p['span'][0]]
                )
                post_halfwidth = HALFWIDTH_REPTN.match(
                    text[p['span'][1] : p['span'][1] + 1]
                )
                # If the parens are surrounded half width characters, replace
                # its part with a space.
                # E.g. "foo(bar)baz" -> "foo baz",
                #      "ほげ(ふが)もげ" -> "ほげもげ"
                if pre_halfwidth and post_halfwidth:
                    repl = ' '
                else:
                    repl = ''
                subs.append([p['pattern'], repl])

                for r in invalid_content_reptns:
                    if r.search(p['content']):
                        break
                else:
                    ret.append(p['content'])

            for pattern, repl in subs:
                text = re.sub(pattern, repl, text)

    ret.insert(0, text)
    return ret

def clean_split_text(
        text: str,
        subs: list[list[str | re.Pattern, str]] = CLEAN_TEXT_SUBS,
        sentence_sep: str | re.Pattern = SENTENCE_SEP_REPTN,
        sentence_pattern: str | re.Pattern = SENTENCE_REPTN,
        parens: list[list[str, str]] | None = PARENS,
        invalid_paren_contents: list[str | re.Pattern] = INVALID_PAREN_CONTENTS,
        separate_paren_contents: bool = True,
        **kwargs
    ):
    """ Cleans the given string up, and splits into sentences.

    The characters in `text` are lowered, and some of them are unified to more
    standard ones before replacing strings (which is performed according to
    `subs`) and separating/removing parentheses (which is performed according to
    `parens` and `invalid_paren_contents`).

    Args:
        text: String to be cleaned up.
        subs: List of lists `[regex, replaced string]` for the text replacement.
            Replacement is performed in the order of the list.
        sentence_sep: Regular expression of the sentence sepatator.
        sentence_pattern: Regular expression of the valid sentence to be
                          returned.
        parens: List of lists `[start character, end character of parenthesis]`.
                These parentheses (both these characters and their contents) are
                removed from the text.
        separate_paren_contents: If `True`, contents in parentheses are
                                 separated as independent texts.

    Return:
        list [str]: Cleaned sentences.
    """
    if type(sentence_sep) is re.Pattern:
        sentence_sep_reptn = sentence_sep
    else:
        sentence_sep_reptn = re.compile(sentence_sep)
    if type(sentence_pattern) is re.Pattern:
        sentence_reptn = sentence_pattern
    else:
        sentence_reptn = re.compile(sentence_pattern)

    # Unify and lowercase characters.
    # ｱ -> ア, ２ -> 2, （ -> (, … -> ...
    text = unicodedata.normalize('NFKC', text).lower()

    for s in subs:
        if type(s[0]) is re.Pattern:
            text = s[0].sub(s[1], text)
        else:
            text = re.sub(s[0], s[1], text)

    if parens:
        if separate_paren_contents:
            spans = tear_paren_contents(text, parens, invalid_paren_contents)
        else:
            spans = tear_paren_contents(
                text, parens, invalid_paren_contents
            )[:1]
    else:
        spans = [text]

    sentences = [
        remove_extra_whitespaces(space_width_gap(sentence))
        for span in spans for sentence in sentence_sep_reptn.split(span)
    ]

    valid_sentences = [
        sentence for sentence in sentences
        if sentence != '' and sentence_reptn.search(sentence)
    ]

    return valid_sentences

def check_co_exps_exist(morps: list | tuple, greedy: bool = True,
    co_exps: list[list[str | re.Pattern]] = CO_EXPS) -> (
        list[list[str | re.Pattern]]
    ):
    """ Checks if there are words in `morps` that must take co-occurrence
    expressions,

    Args:
        morps: List of morphems.
        greedy: If False, returns as soon as one co-occurrence expression has
                been found.
        co_exps: List of co-occurrence expressions (the list consisted of lists
                 that have 2 regular expression string:
                 `[["expression", "co-occurrence expression"], ...]`).

    Return:
        list: co-occurrence expressions found in morps. See the example below.

    Example:
        ```
        check_co_exps(["もし", "空", "を", "飛べ", "る"])
        >> [["[も若](し|し も)", ["なら", "ば", "たら", "も"]]
        ```
    """
    joined = f" {' '.join(morps)} "
    ret = []
    for co in co_exps:
        mtch = co[0].search(joined) if type(co[0]) is re.Pattern else \
               re.search(co[0], joined)
        if mtch:
            ret.append(co)
            if greedy == False:
                break
    return ret

def check_co_exps_fulfilled(
    morps: list | tuple, greedy_for_fulfilled: bool = True,
    greedy_for_unfulfilled: bool = True,
    co_exps: list[list[str | re.Pattern]] = CO_EXPS) -> (
        dict[str, list[str | re.Pattern]]
    ):
    """ If there are words in `morps` that must take co-occurrence expressions,
    checks for the presence of them.

    Args:
        morps: List of morphems.
        greedy_for_fulfilled: If False, returns as soon as one fulfilled
                              co-occurrence expression has been found.
        greedy_for_unfulfilled: If False, returns as soon as one unfulfilled
                                co-occurrence expression has been found.
        co_exps: List of co-occurrence expressions (the list consisted of lists
                 that have 2 regular expression string:
                 `[["expression", "co-occurrence expression"], ...]`).
    Return:
        dict: `fulfilled` and `unfulfilled` co-occurrence expressions found in
              morps. See the example below.
    Example:
        ```
        >>> check_co_exps(["もし", "空", "を", "飛べ", "る", "なら"])
        {"fulfilled": [["[も若](し|し も)", ["なら", "ば", "たら", "も"]],
        "unfulfilled": []}
        >>> check_co_exps(["もし", "空", "を", "飛べ", "る"])
        {"fulfilled": [],
        "unfulfilled": [["[も若](し|し も)", ["なら", "ば", "たら", "も"]]}
        ```
    """
    joined = f" {' '.join(morps)} "
    reptn_co_exps = [[
        # `[expression<str | re.Pattern>,
        #   co-occurrence expressions<list[re.Pattern]>]`
        i[0], [
            j if type(j) is re.Pattern else re.compile(j) for j in i[1]
        ]
    ] for i in co_exps]
    ret = {"fulfilled": [], "unfulfilled": []}

    for co in reptn_co_exps:
        mtch = co[0].search(joined) if type(co[0]) is re.Pattern else \
               re.search(co[0], joined)
        # If the word that take co-occurring expressions exists in `joined`
        if mtch:
            for exp in co[1]:
                # If the co-occurring expression that correlates with `co[0]`
                # exisis in `joined`
                if exp.search(joined):
                    ret["fulfilled"].append(co)
                    if greedy_for_fulfilled == False:
                        return ret
                    break
            else:
                ret["unfulfilled"].append(co)
                if greedy_for_unfulfilled == False:
                    return ret

    return ret
