# 議員発言・行政答弁シミュレーター（バックエンド）

## これは何

会議録から構築された2つのマルコフ連鎖モデル `giin_model` 及び `gyosei_model`によって、議員発言・行政答弁をシミュレートする。

また、会議録コーパスから会議録の一覧・参照、発言者の一覧・参照、発言者の一覧を行う。

## データセット

会議録コーパス及びマルコフ連鎖モデルは、刈谷市議会本会議の会議録 (2019 年 9 月 〜 2023 年 3 月) をもとに構築した。

## 主なファイルの説明

- `app.py`: バックエンドを担う Flask アプリケーション。
- `giin_model_state4.json`: クラス `jptext.JPText` が使用する、議員発言シミュレーション用のマルコフ連鎖モデルデータ。
- `gyosei_model_state4.json`: クラス `jptext.JPText` が使用する、行政答弁シミュレーション用のマルコフ連鎖モデルデータ。
- `jptext.py`: マルコフ連鎖による文書生成等を行うクラス `jptext.JPText` (`markovify.text.Text` を継承し、日本語文章用に改良したもの) を提供する。
- `mkmamodel.py`: マルコフ連鎖モデルデータ `giin_model` (議員発言シミュレーション用) と `gyosei_model` (行政答弁シミュレーション用) を、`resource.sqlite3` から作成する。
- `resource.sqlite3`: 会議録コーパス (会議録、発言、発言者のデータベース)。
- `txtsplit.py`: 文章の形態素解析を行う。
- `txtutils.py`: テキストクリーニングや呼応表現の判定など、文章の取り扱いに関する各種処理を担う。

## インストール

### Python のインストール

実行環境に [Python](https://www.python.org/) がインストールされていることを確認したのち、以下の手順を実行する。

### 依存ライブラリのインストール

本リポジトリをカレントディレクトリに設定し、以下のコマンドで必要なライブラリをインストールする。

```
pip install -r requirements.txt
```

あわせて、以下のコマンドで [Unidic](https://pypi.org/project/unidic/) をダウンロードする (形態素解析に必要)。

```
python -m unidic download
```

### マルコフ連鎖モデルデータの作成

`mkmamodel.py` を実行し、2つのマルコフ連鎖モデルデータ `giin_model_state4.json` (議員発言シミュレーション用) と `gyosei_model_state4.json` (行政答弁シミュレーション用) が作成されたことを確認する。

なお、`mkmamodels.py` 中の関数 `make_giin_gyosei_model()` の引数 `state_size` を変更することで、構築されるマルコフ連鎖の階数 (状態履歴数) を変更することができる (デフォルト: 4)。

## 実行

サーバー実行時のオプション等について、詳細は [Flask のドキュメント](https://flask.palletsprojects.com/) を参照のこと。

### サーバーの開始

本リポジトリをカレントディレクトリに設定し、コマンド `flask --app app.py run` を実行する。

```
$ flask --app app.py run
 * Serving Flask app 'app.py'
 * Running on http://127.0.0.1:5000
```

これを実行すると、`Running on` に続けて表示されているアドレスにサーバーが展開される。デフォルトではローカルホスト 5000 番ポート (`127.0.0.1:5000` または `localhost:5000` または ) にサーバーが展開される。

サーバーを終了するには CTRL+C を押す。

### ネットワーク上のすべての端末からアクセス可能な状態でサーバーを開始する

ホスト環境 (`flask --app app.py run` コマンドを実行したマシン) だけではなく、ネットワーク上のすべての端末からアクセス可能な状態でサーバーを開始するには、オプション `--host=0.0.0.0` を指定してコマンドを実行する。

```
$ flask --app app.py run --host=0.0.0.0
 * Serving Flask app 'app.py'
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
 * Running on http://192.168.x.x:5000
```

上記の場合、ネットワーク上の端末からは、`192.168.x.x:5000` (`<実行環境のIPアドレス>:5000`) からアクセスできる。

### 任意のポート番号でサーバーを開始する

任意のポート番号でサーバーを開始されるようにするには、`--port` オプションを指定してコマンドを実行する。例えば 8000 番で開始されるようにするには以下のようにする。

```
$ flask --app app.py run --port=8000
 * Serving Flask app 'app.py'
 * Running on http://127.0.0.1:8000
```
