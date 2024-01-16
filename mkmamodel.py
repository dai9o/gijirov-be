import json
import sqlite3

from jptext import JPText

def make_giin_gyosei_model(db_path:str, make_giin_model:bool=True,
                           make_gyosei_model:bool=True, **kwargs):
    """
    Return a tuple of markov models `(giin_model, gyosei_model)`.
    kwargs are passed to `JPText` constructor.
    """
    giin_model, gyosei_model = None, None

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    if make_giin_model == True:
        cur.execute(f"SELECT parsed_sentences FROM sections WHERE type=1")
        parsed_sentences = []
        for fields in cur.fetchall():
            parsed_sentences += json.loads(fields[0])
        giin_model = JPText("", parsed_sentences=parsed_sentences, **kwargs)

    if make_gyosei_model == True:
        cur.execute(f"SELECT parsed_sentences FROM sections WHERE type=3")
        parsed_sentences = []
        for fields in cur.fetchall():
            parsed_sentences += json.loads(fields[0])
        gyosei_model = JPText("", parsed_sentences=parsed_sentences, **kwargs)

    cur.close()
    conn.close()

    return giin_model, gyosei_model

if __name__ == "__main__":
    giin_model, gyosei_model = make_giin_gyosei_model(
        "./resource.sqlite3", state_size=4
    )

    # JSON ファイルとして保存
    giin_model_filename = "giin_model_state{giin_model.state_size}.json"
    gyosei_model_filename = f"gyosei_model_state{gyosei_model.state_size}.json"

    with open(giin_model_filename, "w", newline="\n") as f:
        f.write(giin_model.to_json())
    print(f"Giin model has been saved as '{giin_model_filename}'.")

    with open(gyosei_model_filename, "w", newline="\n") as f:
        f.write(gyosei_model.to_json())
    print(f"Gyosei model has been saved as '{gyosei_model_filename}'.")
