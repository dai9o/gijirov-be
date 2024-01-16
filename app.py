import json
import re
import sqlite3

import markovify

from flask import abort, Flask, request
from flask_cors import CORS

from jptext import JPText
from txtsplit import split_into_morps
from txtutils import KANA_REGEX, KANJI_REGEX, chunk_and_split

with open("giin_model_state4.json") as f:
    giin_model = JPText.from_json(f.read())
    print(f"Giin model: state_size={giin_model.state_size}")
with open("gyosei_model_state4.json") as f:
    gyosei_model = JPText.from_json(f.read())
    print(f"Gyosei model: state_size={gyosei_model.state_size}")

GIIN_MIN_WORDS, GIIN_MAX_WORDS = 17, 21
GYOSEI_MIN_WORDS, GYOSEI_MAX_WORDS = 12, 30
DEFAULT_MAKE_SENTENCE_KWARGS = {
    "test_output": False,
    "reject_co_exps": True,
    "tries": 10,
    # ですます調の文章
    "allowed_output_regex": re.compile(
        f"^([ 'a-z]|{KANA_REGEX}|{KANJI_REGEX})+(([でま](し(た|ょう)|す)|ません)[かよ]?ね?|ませ)$"
    ),
    "verbose": True
}

app = Flask(__name__)
CORS(app)

@app.route("/search", methods=["POST"])
def search_sections():
    def snippet_match(kws:list[str], sentences:list[list[str]] | str,
                      max_chars:int=100):
        if type(sentences) is str:
            joined_sentences = sentences
        else:
            joined_sentences = " | ".join([" ".join(grams) for grams in sentences])

        ind = joined_sentences.index(kws[0])
        ret = joined_sentences[joined_sentences.index(kws[0]):][:max_chars]
        if len(ret) == 40:
            ret += " (…)"
        if ind != 0:
            ret = f"(…) {ret}"
        return ret

    receive = request.get_json()

    if receive["splitQuery"] == True:
        kws = chunk_and_split(split_into_morps, receive["query"].lower())
    else:
        kws = receive["query"].lower().split(" ")
    kws_like =  [f"%{kw}%" for kw in kws]  # SQL 文の LIKE 用キーワード

    if receive["target"] == "content":
        target_col = "content"
    elif receive["target"] == "parsedSentences":
        target_col = "parsed_sentences"
    else:
        abort(500)

    where_cond = " AND ".join([f"{target_col} LIKE ?" for _ in kws])

    conn = sqlite3.connect("resource.sqlite3")
    cur = conn.cursor()

    cur.execute(
        f"SELECT COUNT(*) FROM sections WHERE {where_cond}", kws_like
    )
    total_items = cur.fetchone()[0]

    cur.execute(
        f"SELECT id, council_id, speaker_id, type, role, {target_col} FROM sections WHERE {where_cond} LIMIT ? OFFSET ?",
        kws_like + [receive["fetchItems"], receive["fetchOffset"]],
    )

    items = [{
        "id": fields[0],
        "councilID": fields[1],
        "speakerID": fields[2],
        "type": fields[3],
        "role": fields[4],
        "snippetSentence": snippet_match(
            kws,
            json.loads(fields[5]) if target_col == "parsed_sentences" else fields[5]
        )
    } for fields in cur.fetchall()]

    for item in items:
        cur.execute(
            f"SELECT name, held_on FROM councils WHERE id='{item['councilID']}'"
        )
        council_records = cur.fetchall()
        if len(council_records) == 1:
            item["councilName"], item["councilDate"] = council_records[0]
        else:
            item["councilName"], item["councilDate"] = "", ""

        cur.execute(f"SELECT name, party FROM speakers WHERE id='{item['speakerID']}'")
        speaker_records = cur.fetchall()
        if len(speaker_records) == 1:
            item["speakerName"], item["speakerParty"] = speaker_records[0]
        else:
            item["speakerName"], item["speakerParty"] = "", ""

    cur.close()
    conn.close()

    return {
        "totalItems": total_items,
        "items": items,
        "kws": kws
    }

@app.route("/councils", methods=["POST"])
def get_councils():
    receive = request.get_json()

    conn = sqlite3.connect("resource.sqlite3")
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM councils")
    total_items = cur.fetchone()[0]

    cur.execute(
        "SELECT id, name, held_on, retrieved_at, url FROM councils ORDER BY held_on LIMIT ? OFFSET ?",
        [receive["fetchItems"], receive["fetchOffset"]]
    )
    items = [
        {
            "id": fields[0],
            "name": fields[1],
            "heldOn": fields[2],
            "retrievedAt": fields[3],
            "url": fields[4]
        }
        for fields in cur.fetchall()
    ]

    cur.close()
    conn.close()

    return {
        "totalItems": total_items,
        "items": items
    }

@app.route("/council", methods=["POST"])
def view_council():
    receive = request.get_json()

    conn = sqlite3.connect("resource.sqlite3")
    cur = conn.cursor()

    cur.execute(
        "SELECT name, held_on, retrieved_at, url FROM councils WHERE id=?",
        [receive["id"]]
    )
    council_records = cur.fetchall()
    if len(council_records) == 0:
        abort(404)
    elif len(council_records) > 1:
        abort(500)

    cur.execute(
        "SELECT id, speaker_id, type, role, content FROM sections WHERE council_id=? ORDER BY position",
        [receive["id"]]
    )
    section_records = cur.fetchall()

    ret = {
        "name": council_records[0][0],
        "heldOn": council_records[0][1],
        "retrievedAt": council_records[0][2],
        "url": council_records[0][3],
        "sections": [
            {
                "id": section_record[0],
                "speakerID": section_record[1],
                "type": section_record[2],
                "role": section_record[3],
                "content": section_record[4]
            }
            for section_record in section_records
        ]
    }

    for section in ret["sections"]:
        cur.execute(
            "SELECT name, party FROM speakers WHERE id=?",
            [section["speakerID"]]
        )
        speaker_records = cur.fetchall()
        if len(speaker_records) == 1:
            section["speakerName"], section["speakerParty"] = speaker_records[0]
        else:
            section["speakerName"], section["speakerParty"] = "", ""

    cur.close()
    conn.close()

    return ret

@app.route("/speakers", methods=["POST"])
def get_speakers():
    receive = request.get_json()

    conn = sqlite3.connect("resource.sqlite3")
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM speakers WHERE id != ''")
    total_items = cur.fetchone()[0]

    cur.execute(
        "SELECT id, name, kana_family_name, kana_given_name, birth_year, gender, party, faction, address FROM speakers WHERE id != '' LIMIT ? OFFSET ?",
        [receive["fetchItems"], receive["fetchOffset"]]
    )
    items = [
        {
            "id": fields[0],
            "name": fields[1],
            "kanaFamilyName": fields[2],
            "kanaGivenName": fields[3],
            "birthYear": fields[4],
            "gender": fields[5],
            "party": fields[6],
            "faction": fields[7],
            "address": fields[8]
        }
        for fields in cur.fetchall()
    ]

    cur.close()
    conn.close()

    return {
        "totalItems": total_items,
        "items": items
    }

@app.route("/speaker", methods=["POST"])
def view_speaker():
    receive = request.get_json()

    conn = sqlite3.connect("resource.sqlite3")
    cur = conn.cursor()

    cur.execute(
        "SELECT name, kana_family_name, kana_given_name, birth_year, gender, party, faction, address FROM speakers WHERE id=?",
        [receive["id"]]
    )
    speaker_records = cur.fetchall()

    cur.close()
    conn.close()

    if len(speaker_records) == 0:
        abort(404)
    elif len(speaker_records) > 1:
        abort(500)

    ret = {}
    (
        ret["name"],
        ret["kanaFamilyName"],
        ret["kanaGivenName"],
        ret["birthYear"],
        ret["gender"],
        ret["party"],
        ret["faction"],
        ret["address"]
    ) = speaker_records[0]
    
    return ret

@app.route("/generate", methods=["POST"])
def generate():
    receive = request.get_json()

    if receive["model"] == "giin":
        model = giin_model
        min_words, max_words = GIIN_MIN_WORDS, GIIN_MAX_WORDS
    elif receive["model"] == "gyosei":
        model = gyosei_model
        min_words, max_words = GYOSEI_MIN_WORDS, GYOSEI_MAX_WORDS
    else:
        abort(500)

    beginning = tuple(
        model.word_split(receive["prompt"].removeprefix("「").lower())
    )
    over_state_size = len(beginning) > model.state_size
    strict = not over_state_size and receive["prompt"].startswith("「")

    if beginning:  # When beginning is not empty
        try:
            output = model.make_sentence_with_start(
                beginning=beginning[-model.state_size:],
                strict=strict,
                min_words=min_words,
                max_words=max_words,
                **DEFAULT_MAKE_SENTENCE_KWARGS
            )
        except KeyError:  # prompt で始まる文章が model に存在しないときなど
            output = None
        except markovify.text.ParamError:  # promot が state_size を超える単語数のときなど
            output = None
    else:
        output = model.make_sentence(
            min_words=min_words,
            max_words=max_words,
            **DEFAULT_MAKE_SENTENCE_KWARGS
        )

    if not output:
        abort(500)

    if receive["wakachi"] == True:
        formatted_sentence = " ".join(output["words"])
    else:
        formatted_sentence = output["sentence"]

    if over_state_size:
        formatted_sentence = f"… {formatted_sentence}"
    elif strict:
        formatted_sentence = f"「{formatted_sentence}」"

    return {
        "sentence": formatted_sentence,
        "existsInCorpus": output["sentence"] in model.rejoined_text
    }
