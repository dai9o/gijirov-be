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


def split_into_bunsetsu(text:str, nobreak_dependent:bool=False):
    """Splits Japanese string into several bunsetsu.

    Based on https://qiita.com/shimajiroxyz/items/e44058af8b036f5354aa (credit:
    shimajiroxyz).

    Args:
        text (str): String data to split.
        nobreak_dependent (bool): If `True`, dependent (非自立) nouns (e.g.
                                  "もの" / "こと" right after verbs/adjectives,
                                  "の" in the sense of "things" / "stuffs" as in
                                  "やったのか") and dependent verbs (e.g. "いる"
                                  as in "やっている") will not be parsed as
                                  separators of bunsetsu.

    Return:
        list (str): List of bunsetsu.
    """
    m_result = m.parse(text).splitlines()
    m_result = m_result[:-1]  # 最後の1行は不要な行なので除く
    # 文節の切れ目を検出するための品詞リスト
    break_pos = ['名詞', '代名詞', '動詞', '接頭辞', '副詞', '感動詞', '形容詞',
                 '形容動詞', '形状詞', '連体詞']
    wakachi = ['']  # 分かち書きのリスト
    afterPrepos = False  # 接頭詞の直後かどうかのフラグ
    afterSahenNoun = False  # サ変接続名詞の直後かどうかのフラグ
    for v in m_result:
        if '\t' not in v: continue
        surface = v.split('\t')[0]  # 表層系
        pos = v.split('\t')[1].split(',')  # 品詞など
        # 品詞細分類（各要素の内部がさらに'/'で区切られていることがあるので、
        # ','でjoinして、inで判定する)
        pos_detail = ','.join(pos[1:4])
        # この単語が文節の切れ目とならないかどうかの判定
        noBreak = pos[0] not in break_pos
        noBreak = noBreak or '接尾' in pos_detail
        noBreak = noBreak or (pos[0] == '動詞' and 'サ変接続' in pos_detail)
        if nobreak_dependent:
            # 非自立な名詞・動詞を文節の切れ目としないようにする
            noBreak = noBreak or '非自立' in pos_detail
        noBreak = noBreak or afterPrepos
        noBreak = noBreak or (afterSahenNoun and pos[0] == '動詞' and \
                              pos[4] == 'サ変・スル')
        if noBreak == False:
            wakachi.append("")
        wakachi[-1] += surface
        afterPrepos = pos[0] == '接頭辞'
        afterSahenNoun = 'サ変接続' in pos_detail
    if wakachi[0] == '': wakachi = wakachi[1:]  # 最初が空文字のとき削除する
    return wakachi
