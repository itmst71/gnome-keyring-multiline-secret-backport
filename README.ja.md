# GNOME Keyring 複数行テキストシークレットのバックポート

[English (canonical)](README.md) | **日本語**

英語版が正本です。翻訳に相違がある場合は英語版を優先します。

**なぜ必要か：** 対象のGNOME Keyringには、アプリケーションが**空パスワードのKeyringへ複数行の秘密情報を保存すると、ファイルを読み込めなくする**不具合があります。そのセッション中は利用できても、次回ログインやデーモン起動時に読込に失敗し、保存済みの認証情報が消えたように見える場合があります。このキットは、値を正しくエスケープして破損を防ぐ最小限の修正を加えたUbuntuパッケージをビルドします。**既に破損したKeyringの修復や、失われた認証情報の復旧は行いません。**

> **Ubuntu 24.04／26.04向けの非公式ローカルバックポートキットです。** GNOMEやUbuntuの公式プロジェクトではなく、バイナリ配布も行いません。公式のセキュリティ更新ではありません。

共通のパッチ・テスト・ビルドツールを一つのリポジトリで管理し、明示的なターゲットプロファイルでUbuntuごとのソース版とビルド環境を分離します。自分の環境に合ったパッケージをビルドしてください。別のUbuntu版向けのパッケージを使用したり、他人のビルドを信頼済みの公式成果物として扱ったりしないでください。

## 対象範囲

問題のあるUTF-8テキストシークレットの保存処理では、`g_key_file_set_value()`を使用していました。このため改行がGKeyFileの値として不正な形式のまま出力され、次回のデーモン起動時にテキスト形式のKeyringを読み込めなくなる場合があります。

[`patches/0001-escape-multiline-textual-secrets.patch`](patches/0001-escape-multiline-textual-secrets.patch)は、[GNOME gnome-keyring MR !111](https://gitlab.gnome.org/GNOME/gnome-keyring/-/merge_requests/111)と同等の動作を実装します。

- UTF-8保存処理の`g_key_file_set_value()`を`g_key_file_set_string()`に置き換えます。
- GNOMEの複数行データに対する保存・再読込・取得の回帰テストを追加します。

実行時の処理変更は、このAPIの置き換えだけです。パッチは上流の方式に沿った回帰テストも登録しますが、バイナリシークレットの処理、Secret Serviceプロトコル、Keyringの暗号化、デーモンの起動・ロック解除動作は変更しません。

このリポジトリには、所有者の実環境を操作するD-Bus／Secret Serviceの結合テスト用ヘルパーを意図的に含めていません。合成データによるGLibテストが示すのはシリアライズの動作だけであり、個々の利用者のKeyringやセッションをまたぐ永続性を検証した証拠ではありません。

## ターゲットと固定された入力

| ターゲット | Ubuntu | ソース版 | ローカルパッケージ版 |
|---|---|---|---|
| `ubuntu24.04` | 24.04 / noble | `46.1-2ubuntu0.2` | `46.1-2ubuntu0.2+local1` |
| `ubuntu26.04` | 26.04 / resolute | `50.0-1` | `50.0-1ubuntu0.0+local1` |

検証対象のアーキテクチャは**amd64のみ**です。Ubuntuのサポート期間内であっても、その後のすべてのソース改訂版にこのパッチが対応するという意味ではありません。

[24.04プロファイル](targets/ubuntu24.04.json)と[26.04プロファイル](targets/ubuntu26.04.json)が、ソースURL、SHA-256、署名者のフィンガープリント、ベースイメージのダイジェスト、スナップショット日時の正本です。共通の取得・ビルド処理は、3つのソースファイルのハッシュと署名付き`.dsc`を検証します。署名検証には、選択した公開署名鍵だけを含む一時Keyringを使用します。展開前には、ビルド用にコピーした入力に対して再度認証を行います。

ビルド入力は固定していますが、**成果物のバイト単位での再現性は保証していません**。キャッシュ、作業ディレクトリ、出力先はターゲットごとに分離しています。既存のパッケージは上書きせず、失敗したビルドの作業ディレクトリも保持します。

> 最小構成のベースイメージにはCA証明書バンドルがありません。Dockerfileは最初のパッケージ索引更新と`ca-certificates`のインストールに限りHTTPSのピア検証を無効化しますが、APTの署名検証は維持します。それ以降のスナップショット取得では通常のTLS検証を行います。

## 再ビルドとパッケージテスト

必要なものはLinux、Python 3.10以降、利用可能なDockerデーモン、イメージ・依存関係・ソースの取得に必要なネットワーク接続です。リポジトリのルートから通常ユーザーで実行してください。パッケージのビルドは、そのユーザーのUID/GIDで実行されます。
CIランナーなどUIDが1000以外でもD-Busテストが動くよう、ビルダー内に該当UID/GIDのユーザー・グループがなければ追加します。ホストのアカウントファイルはマウントもコピーもしません。

```sh
# Select the target explicitly; there is no default.
sh scripts/build.sh ubuntu24.04
sh scripts/build.sh ubuntu26.04
```

各コマンドは固定されたコンテナをビルドし、ソースを認証して共通パッチを適用した後、`dpkg-buildpackage -b -uc -us -j4`を実行します。ディストリビューションのパッケージテストと、追加した複数行データの往復テストを含みます。`nocheck`は拒否します。パッケージビルド用コンテナのネットワークは無効で、チェックアウトは読み取り専用です。デスクトップのセッションバスや実際のKeyringはマウントしません。ホストへのインストールやサービス再起動も行いません。

生成された`gnome-keyring`パッケージのみを`dist/<target>/`へコピーします。それ以外のビルド成果物とログは`.build/<target>/work/`に残ります。生成ファイルはコミット・公開・アップロードしないでください。パッケージは次のように確認できます。

```sh
dpkg-deb -f dist/ubuntu26.04/gnome-keyring_50.0-1ubuntu0.0+local1_amd64.deb \
  Package Version Architecture
sha256sum dist/ubuntu26.04/*.deb
```

前回のパッケージを上書きせず再ビルドするには、新しい出力先を指定します。

```sh
sh scripts/build.sh ubuntu26.04 --dist-dir "$PWD/dist/ubuntu26.04-rerun"
```

下位コマンドの`scripts/fetch-source.sh`と`scripts/build-local-package.sh`もターゲット指定が必須です。従来の引数なしの呼出しには対応しません。ソース・作業・出力ディレクトリの指定方法は`python3 scripts/backport.py --help`を参照してください。直接ビルドするコマンドは、Ubuntuの版やアーキテクチャが一致しない環境を拒否します。

## テストと公開前の検査

ビルドツールと英日ドキュメントのオフラインテストにはPythonが必要です。版の大小関係の検査には追加で`dpkg`を使用し、見つからなければその検査をスキップします。公開範囲の検査は、`.build/`や`dist/`を作成する前の、ソースだけのツリーで実行してください。Gitで無視されていても、生成物や私的データがある場合は意図的に拒否します。CIはこの検査後、両ターゲットをマトリクスでビルドします。CIが設定されていることは、特定の未公開コミットがGitHub上のCIに合格したことを意味しません。

```sh
python3 -B tests/test-build-kit.py -v
python3 -B tests/verify-public-tree.py
```

独立したCテストは固定の非機密な複数行文字列を使用します。CコンパイラとGLib開発用ファイルが必要です。Secret Serviceとは独立しており、Keyringにアクセスしません。いずれかの対象ビルダー内で実行してください。

```sh
# Expected RED: raw GKeyFile writing aborts on a reload attempt.
test_dir=$(mktemp -d)
ulimit -c 0
gcc -std=c11 -Wall -Wextra -Werror tests/test-keyfile-multiline-roundtrip.c \
  $(pkg-config --cflags --libs glib-2.0) -o "$test_dir/keyfile-test-raw"
"$test_dir/keyfile-test-raw"

# GREEN: the escaping writer round-trips the same value.
gcc -std=c11 -Wall -Wextra -Werror -DUSE_ESCAPING_WRITER \
  tests/test-keyfile-multiline-roundtrip.c \
  $(pkg-config --cflags --libs glib-2.0) -o "$test_dir/keyfile-test-escaped"
"$test_dir/keyfile-test-escaped"
```

raw版のテストは意図的に失敗する想定です。そのREDを確認した後に、エスケープ版を実行してください。これらのテストだけでは、実際のデスクトップでログアウト・ログインをまたいでデータが保持されることまでは確認できません。

## インストールとロールバック

インストールは意図的に手動操作としています。まず既存のKeyringを非公開の場所へバックアップし、生成したパッケージを確認して、**使用中のUbuntuと一致するターゲットだけ**をインストールしてください。Ubuntu 26.04での例です。

```sh
sudo apt install ./dist/ubuntu26.04/gnome-keyring_50.0-1ubuntu0.0+local1_amd64.deb
```

通常のログアウト・ログインを行い、デスクトップセッションがインストール済みのデーモンを起動するようにしてください。実行中のセッションでユーザーサービスだけを再起動しても、新規のデスクトップログインと同等ではなく、永続性の適切な検証にはなりません。

記載したUbuntu標準版が引き続き取得可能な場合は、次のように戻せます。ただし、問題のある保存処理に戻す操作であり、破損したデータを復元するものではありません。

```sh
sudo apt install --reinstall --allow-downgrades gnome-keyring=50.0-1
```

24.04では表にある版と`dist/ubuntu24.04/`の対応パッケージを使用してください。ローカル版は元のパッケージより新しく、通常の次回Ubuntuセキュリティ改訂版（それぞれ`46.1-2ubuntu0.3`、`50.0-1ubuntu0.1`）より古いと判定される版番号です。これらは大小関係の例であり、その改訂版が公開済みだという意味ではありません。26.04の`ubuntu0.0+local1`という接尾辞は、`50.0-1ubuntu0.1`より新しいと判定されてしまう`50.0-1+local1`を避けるために使用しています。すべての公式リビルドが必ずローカル版より新しくなるわけではないため、`apt-cache policy gnome-keyring`を確認し、必要に応じて修正を新しい版へ載せ替えてください。公式更新やOSアップグレードにより、修正が不具合のある版に置き換わる場合もあります。**パッケージ更新やディストリビューションのアップグレード後は再確認してください。** セキュリティ更新を妨げる無期限のholdは行わないでください。新しいソース改訂版を追加する前に公式ソースへ修正が取り込まれていないか確認し、固定入力を更新してパッケージテストをすべて再実行してください。共通ツールやパッチを変更する際は、維持対象の両ターゲットを同じレビューで確認してください。既存の破損には別途復旧手順が必要です。UIに表示されないという理由だけでKeyringを削除しないでください。

## 公開範囲の境界

Keyringファイル、認証情報、秘密鍵、Cookie、データベースのダンプ、ネットワークキャプチャ、D-Busログ、取得したソースのキャッシュ、ビルドディレクトリ、パッケージ成果物をこのリポジトリへ追加しないでください。`.gitignore`は一般的なローカル生成物を除外し、`tests/verify-public-tree.py`は許可されていないファイルや個人のファイルシステムパスを拒否します。

上流への帰属表記は[NOTICE](NOTICE)、ファイルごとのライセンス区分は[LICENSE](LICENSE)を参照してください。貢献や報告の範囲は[CONTRIBUTING.md](CONTRIBUTING.md)と[SECURITY.md](SECURITY.md)に記載しています。
