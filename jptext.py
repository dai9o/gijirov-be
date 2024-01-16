import functools
import json
import random
import re

from markovify.text import (Text, ParamError, DEFAULT_MAX_OVERLAP_RATIO,
                            DEFAULT_MAX_OVERLAP_TOTAL, DEFAULT_TRIES)
from markovify.chain import Chain, BEGIN

from txtsplit import split_into_morps
from txtutils import (KANA_REGEX, KANJI_REGEX, clean_split_text,
                      chunk_and_split, join_chunks, check_co_exps_exist,
                      check_co_exps_fulfilled)

DEFAULT_ALLOWED_OUTPUT_REPTN = re.compile(
    f"^([ 'a-z]|{KANA_REGEX}|{KANJI_REGEX})+$"
)

def trim_top_words(words: list[str] | tuple[str], start_from: int = 0):
    """ Trims words from the top of `words`.

    Return:
        tuple[list[str], list[str]]: Tuple of trimmed and remained words list.

    Example:
        ```
        >>> x = trim_top_words(["foo", "bar", "baz"], 1)
        >>> for i in x: i
        (["foo"], ["bar", "baz"])
        (["foo", "bar"], ["baz"])
        (["foo", "bar", "baz"], [])
        ```
    """
    for i in range(start_from, len(words)):
        yield words[:i], words[i:]

class JPText(Text):
    def __init__(
        self,
        input_text,
        state_size=2,
        chain=None,
        parsed_sentences=None,
        retain_original=True,
        well_formed=False,
        reject_reg="",
        **kwargs
    ):
        """
        A modified version of `markovify.Text` for Japanese text.

        input_text: A string.
        state_size: An integer, indicating the number of words in the model's
                    state.
        chain: A trained markovify.Chain instance for this text, if
               pre-processed.
        parsed_sentences: A list of lists, where each outer list is a "run"
                          of the process (e.g. a single sentence), and each
                          inner list contains the steps (e.g. words) in the run.
                          If you want to simulate an infinite process, you can
                          come very close by passing just one, very long run.
        retain_original: Indicates whether to keep the original corpus.
        well_formed: Indicates whether sentences should be well-formed,
                     preventing unmatched quotes, parenthesis by default, or a
                     custom regular expression
                     can be provided.
        reject_reg: If well_formed is True, this can be provided to override the
                    standard rejection pattern.

        `**kwargs` are pased to `self.generate_copus()`.
        """
        # Enable cache for the method
        lru_cache = functools.lru_cache(maxsize=1)
        self.find_init_states_from_chain = lru_cache(
            self._find_init_states_from_chain
        )

        self.well_formed = well_formed
        if well_formed and reject_reg != "":
            self.reject_pat = re.compile(reject_reg)

        can_make_sentences = parsed_sentences is not None or \
                             input_text is not None
        self.retain_original = retain_original and can_make_sentences
        self.state_size = state_size

        if self.retain_original:
            self.parsed_sentences = parsed_sentences or list(
                self.generate_corpus(input_text, **kwargs)
            )

            # Rejoined text lets us assess the novelty of generated sentences
            self.rejoined_text = self.sentence_join(
                map(self.word_join, self.parsed_sentences)
            )
            self.chain = chain or Chain(self.parsed_sentences, state_size)
        else:
            if not chain:
                parsed = parsed_sentences or self.generate_corpus(input_text,
                                                                  **kwargs)
            self.chain = chain or Chain(parsed, state_size)

    def to_json(self, *, skipkeys=False, ensure_ascii=False,
                check_circular=True, allow_nan=True, cls=None, indent=None,
                separators=None, default=None, sort_keys=False, **kwargs):
        """
        Returns the underlying data as a JSON string.

        All args are passed to `json.dumps()`.
        """
        return json.dumps(self.to_dict(), skipkeys=skipkeys,
                          ensure_ascii=ensure_ascii,
                          check_circular=check_circular, allow_nan=allow_nan,
                          cls=cls, indent=indent, separators=separators,
                          default=default, sort_keys=sort_keys, **kwargs)

    def sentence_split(self, text, **kwargs):
        """
        Splits full-text string into a list of sentences.

        `**kwargs` are passed to `clean_split_text()`.
        """
        return clean_split_text(text, **kwargs)

    def word_split(self, sentence, splitter=None, **kwargs):
        """
        Splits a sentence into a list of words.

        `**kwargs` are passed to `chunk_and_split()`.

        Args:
            sentence (str): Sentence to be split into words.
            splitter (function): Callback function for `chunk_and_split()`.
                                 Splits string into some units (e.g. words).
                                 Default is `split_into_morps()`.
        """
        if splitter is None:
            splitter = split_into_morps
        return chunk_and_split(splitter, sentence, **kwargs)

    def word_join(self, words):
        """
        Re-joins a list of words into a sentence.
        """
        return join_chunks(words)

    def generate_corpus(self, text, **kwargs):
        """
        Given a text string, returns a list of lists; that is, a list of
        "sentences," each of which is a list of words. Before splitting into
        words, the sentences are filtered through `self.test_sentence_input`

        `**kwargs` are passed to `self.sentence_split()` and
        `self.word_split()`.
        """
        if isinstance(text, str):
            sentences = self.sentence_split(text, **kwargs)
        else:
            sentences = []
            for line in text:
                sentences += self.sentence_split(line, **kwargs)
        passing = filter(self.test_sentence_input, sentences)
        #runs = map(self.word_split, passing)
        runs = [self.word_split(sentence, **kwargs) for sentence in passing]
        return runs

    def test_sentence_output(self, words: list[str],
                             max_overlap_ratio=DEFAULT_MAX_OVERLAP_RATIO,
                             max_overlap_total=DEFAULT_MAX_OVERLAP_TOTAL, *,
                             verbose = False, **kwargs):
        """
        Given a generated list of words, accept or reject it. This one rejects
        sentences that too closely match the original text, namely those that
        contain any identical sequence of words of X length, where X is the
        smaller number of (a) `max_overlap_ratio` (default: 0.7) of the total
        number of words, and (b) `max_overlap_total` (default: 15).

        Return:
            bool: True if there is no similar sentence in the original text.
            dict: When `verbose == True`.
                  `{"ok": bool , "gramJoined": str | None}`.
        """
        # Reject large chunks of similarity
        overlap_ratio = round(max_overlap_ratio * len(words))
        overlap_max = min(max_overlap_total, overlap_ratio)
        overlap_over = overlap_max + 1
        gram_count = max((len(words) - overlap_max), 1)
        grams = [words[i : i + overlap_over] for i in range(gram_count)]
        for g in grams:
            gram_joined = self.word_join(g)
            if gram_joined in self.rejoined_text:
                if verbose == True:
                    return {"ok": False, "gramJoined": gram_joined}
                else:
                    return False

        if verbose == True:
            return {"ok": True}
        else:
            return True

    def make_sentence(
        self, init_state: tuple[str] = None, *, tries: int = DEFAULT_TRIES,
        test_output: bool = True, max_words: int | None = None,
        min_words: int | None = None, reject_co_exps: bool = False,
        reject_unfulfilled_co_exps: bool = False,
        allowed_output_regex: str | re.Pattern | None =  DEFAULT_ALLOWED_OUTPUT_REPTN,
        **kwargs
    ):
        """
        Attempts `tries` (default: 10) times to generate a valid sentence,
        based on the model and `test_sentence_output`. Passes `max_overlap_ratio`
        and `max_overlap_total` to `test_sentence_output`.

        If successful, returns the sentence as a string. If not, returns None.

        Sentence is returned only when it matches for `allowed_output_regex.

        If `init_state` (a tuple of `self.chain.state_size` words) is not
        specified, this method chooses a sentence-start at random, in accordance
        with the model.

        If `test_output` is set as False then the `test_sentence_output` check
        will be skipped.

        If `max_words` or `min_words` are specified, the word count for the
        sentence will be evaluated against the provided limit(s).

        If reject_co_exps == True, words in the sentence are passed to
        `check_co_exps_exist()`, and tries making a sentence again when the
        sentence includes a co-occurrence expression.

        If reject_unfulfilled_co_exps == False and
        reject_unfulfilled_co_exps == True, output words in the sentence are
        passed to `check_co_exps_fulfilled()`, and tries making a sentence again
        when the sentence includes an unfulfilled co-occurrence expression.

        If verbose == True, returns a dictionary that has detailed information,
        instead of a single string.

        `**kwargs` are passed to `self.test_sentence_output()`.
        """
        verbose = kwargs.get("verbose", False)

        if type(allowed_output_regex) is str:
            allowed_output_reptn = re.compile(allowed_output_regex)
        else:
            allowed_output_reptn = allowed_output_regex

        if init_state is None:
            prefix = []
        else:
            prefix = list(init_state)
            for word in prefix:
                if word == BEGIN:
                    prefix = prefix[1:]
                else:
                    break

        rejected_outputs = []
        for counter in range(tries):
            words = prefix + self.chain.walk(init_state)
            output = {
                "counter": counter,
                "words": words,
                "wordCount": len(words),
            }

            if (max_words is not None and output["wordCount"] >= max_words) or (
                min_words is not None and output["wordCount"] <= min_words
            ):
                if verbose == True:
                    rejected_outputs.append(output)
                continue  # pragma: no cover # see coveragepy/issues/198

            output["sentence"] = self.word_join(words)
            if allowed_output_reptn:
                output["isAllowedPattern"] = allowed_output_reptn.search(
                    output["sentence"]
                ) is not None
                if output["isAllowedPattern"] == False:
                    if verbose == True:
                        rejected_outputs.append(output)
                    continue

            if test_output and hasattr(self, "rejoined_text"):
                output["testSentenceOutput"] = self.test_sentence_output(
                    words=words, **kwargs
                )
                if verbose == True:
                    if output["testSentenceOutput"]["ok"] == False:
                        rejected_outputs.append(output)
                        continue
                else:
                    if output["testSentenceOutput"] == False:
                        continue

            if reject_co_exps == True:
                output["checkCoExpsExist"] = check_co_exps_exist(words,
                                                                 greedy=False)
                if output["checkCoExpsExist"] != []:
                    if verbose == True:
                        rejected_outputs.append(output)
                    continue
            else:
                if reject_unfulfilled_co_exps == True:
                    output["checkCoExpsFulfilled"] = check_co_exps_fulfilled(
                        words, greedy_for_unfulfilled=False
                    )
                    if output["checkCoExps"]["unfulfilled"] != []:
                        if verbose == True:
                            rejected_outputs.append(output)
                        continue

            break
        else:
            return None

        if verbose == True:
            output["rejectedOutputs"] = rejected_outputs
            return output
        else:
            return output["sentence"]

    def make_sentence_with_start(self, beginning: str | tuple[str],
                                 strict: bool = True, tolerate_beginning: bool = False,
                                 **kwargs):
        """
        Tries making a sentence that begins with `beginning` string/tuple,
        which should be a string/tuple of strings of one to `self.state` words
        known to exist in the corpus.

        If strict == True, then markovify will draw its initial inspiration
        only from sentences that start with the specified word/phrase.

        If strict == False, then markovify will draw its initial inspiration
        from any sentence containing the specified word/phrase.

        If tolerate_beginning == True, words at the top of `beginning` are
        abandoned if failed to made the following sentence, and tries continue
        until a sentence can be made successfully.

        **kwargs are passed to `self.make_sentence()` and `self.word_split()`
        (for split `beginning` string).
        """
        verbose = kwargs.get("verbose", False)

        if type(beginning) is str:
            beginning_split = tuple(self.word_split(beginning, **kwargs))
        else:
            beginning_split = beginning

        split_gen = trim_top_words(
            beginning_split,
            # Start trimming the last `self.state_size` words
            # if `tolerate_beginning == True`
            start_from=len(beginning_split) - self.state_size \
                       if tolerate_beginning == True else 0
        )

        for split_abandoned, split in split_gen:
            word_count = len(split)

            if word_count == self.state_size:
                init_states = [split]

            elif 0 < word_count < self.state_size:
                if strict:
                    init_states = [(BEGIN,) * (self.state_size - word_count) + \
                                   split]

                else:
                    init_states = self.find_init_states_from_chain(split)

                    random.shuffle(init_states)
            else:
                err_msg = (
                    f"`make_sentence_with_start` for this model requires a "
                    f"string containing 1 to {self.state_size} words. "
                    f"Yours has {word_count}: {str(split)}"
                )
                raise ParamError(err_msg)

            for init_state in init_states:
                try:
                    output = self.make_sentence(init_state, **kwargs)
                except KeyError as e:
                    if tolerate_beginning == True:
                        continue
                    else:
                        raise KeyError(e)
                if output is not None:
                    if verbose == True:
                        return {
                            "sentenceWithStart": self.word_join(
                                list(split_abandoned) + output["words"]
                            ),
                            "beginningSplit": beginning_split,
                            "split": split,
                            "splitAbondoned": split_abandoned,
                            "initState": init_state,
                            **output,
                        }
                    else:
                        return self.word_join(list(split_abandoned) + [output])

            if tolerate_beginning == False:
                break

        err_msg = (
            f"`make_sentence_with_start` can't find sentence beginning with "
            f"{beginning}"
        )
        raise ParamError(err_msg)

    def _find_init_states_from_chain(self, split):
        """
        Find all chains that begin with the split when
        `self.make_sentence_with_start` is called with strict == False.

        This is a very expensive operation, so lru_cache caches the results of
        the latest query in case `self.make_sentence_with_start` is called
        repeatedly with the same beginning string.
        """
        word_count = len(split)
        return [
            key
            for key in self.chain.model.keys()
            # check for starting with begin as well ordered lists
            if tuple(filter(lambda x: x != BEGIN, key))[:word_count] == split
        ]
