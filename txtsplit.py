import os

import MeCab
import unidic

UNIDIC_DIR = unidic.DICDIR.replace(os.sep, '/')
m = MeCab.Tagger('-d ' + UNIDIC_DIR)  # 形態素出力
mw = MeCab.Tagger('-Owakati -d ' + UNIDIC_DIR)  # 分かち書き出力

def split_into_morps(text:str):
    """Splits Japanese text into morphems.

    Args:
        text (str): String data to split.

    Return:
        list (str): List of morphems.
    """
    return mw.parse(text).strip().split(' ')
