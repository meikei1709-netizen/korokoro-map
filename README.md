# ご当地！ころころにゃんこ コレクションMAP（非公式）

| ファイル | 役割 |
|---|---|
| `index.html` | サイト本体（地図・記録・自分の写真・共有同期） |
| `cats.json` | 公式ページから取り込んだ「地域・名前・位置」（画像なし） |
| `update_cats.py` | 公式ページを読んで `cats.json` を更新するスクリプト |
| `.github/workflows/deploy-site.yml` | GitHub Pages への公開＋毎日の自動取り込み |

## 全体の流れ
① GitHub Pages でサイトを公開 → ② Firebase でデータの置き場を作る → ③ サイトの「☁ 共有・同期」でつなぐ → ④ 家族にリンクを送る

## ① GitHub Pages で公開する
1. GitHub にログインし、右上「＋」→ **New repository**
   - 名前：`korokoro-map`（好きな名前でOK。公開URLの一部になります）
   - **Public** を選ぶ（無料アカウントの GitHub Pages は公開リポジトリのみ。記録・写真はこのリポジトリに入らないので大丈夫です）
   - 「Add a README」などのチェックは付けない
2. このフォルダの中身を、リポジトリに置く（`.github` フォルダも一緒に）
   ```
   cd korokoro-map
   git init -b main
   git add .
   git commit -m "first commit"
   git remote add origin https://github.com/ユーザー名/korokoro-map.git
   git push -u origin main
   ```
   Webの画面だけでやる場合：「uploading an existing file」で `index.html` `cats.json` `update_cats.py` `README.md` をアップロード → 「Add file → Create new file」で、ファイル名の欄に `.github/workflows/deploy-site.yml` と入力（`/` を打つとフォルダになります）し、中身を貼り付けて保存。
3. リポジトリの **Settings → Pages → Build and deployment → Source** を **GitHub Actions** にする
4. **Actions** タブ → 左の `deploy-site` → **Run workflow**（最初の push のときは Pages の設定前なので失敗しています。設定後にもう一度実行）
5. 緑のチェックになったら、`https://ユーザー名.github.io/korokoro-map/` が公開URLです（Settings → Pages にも表示されます）

Actions のログで「公式ページ: 94件」のように出ていれば、公式ページの読み取りも成功しています。

## ② Firebase（無料枠・約10分）
写真もデータベースの中に入れる方式なので、Firebase Storage（有料）は使いません。

1. https://console.firebase.google.com で「プロジェクトを追加」（Googleアナリティクスはオフでよい）
2. 左メニュー「構築」→ **Realtime Database** →「データベースを作成」
   - ロケーションは近い場所（シンガポールなど）、セキュリティルールは「ロックモード」
3. 「ルール」タブに、下をそのまま貼り付けて「公開」
   ```json
   {
     "rules": {
       ".read": false,
       ".write": false,
       "rooms": {
         "$room": {
           ".read": "$room.length >= 20",
           ".write": "$room.length >= 20"
         }
       }
     }
   }
   ```
   「共有リンクに入っている長い秘密のキーを知っている人だけが、その部屋を読み書きできる」という意味です。部屋の一覧は誰にも見えません。
4. 「データ」タブの上に出ているURL（`https://〜.firebasedatabase.app`）をコピー

## ③ サイトでつなぐ
1. 写真を登録してきたブラウザで、**新しい `index.html` を同じ場所に上書きして開く**（別の場所で開くと、これまでの写真は見えません）
   - すでに公開URLで写真を登録している場合は、そのURLを開けばOK
2. 「☁ 共有・同期」→ Firebase のURLを貼る →「共有を作る」（いまの記録・写真がアップロードされます）
3. パソコン内のファイルとして開いている場合は「公開したサイトのURL」欄に ① のURLを入れる
4. 出てきた **編集リンク** を自分のスマホ・家族へ。見るだけでよい人には **閲覧専用リンク**

リンクを開くと自動でつながり、次からはリンク不要です。変更は数秒で反映され、開いている間は1分ごとにも同期します。

### 知っておくこと
- リンクを知っている人は誰でも記録・写真を見られます（編集リンクなら変更も可能）。家族以外には送らないでください。「閲覧専用」は、うっかり編集の防止用で、セキュリティ機能ではありません。
- 同じにゃんこを2人が同時に編集した場合は、あとに保存した方が採用されます（項目ごと・写真ごとに判定）。
- 共有をやめても、サーバー上のデータは消えません。不要になったら Firebase の「データ」タブで削除してください。
- 無料枠（Spark）の目安：保存1GB・ダウンロード月10GB。このサイトの使い方なら十分余裕があります（写真1枚あたり十数KB）。
- 「記録を書き出す／読み込む」は、共有を使わないときのバックアップ・お引っ越し用です。写真も含まれます。

## 新しいにゃんこの自動取り込み
- `deploy-site.yml` が毎日（日本時間 06:17ごろ）公式ページを読み、増えていれば `cats.json` を更新して公開し直します。新しいものは「NEW」表示（45日間）。
- 取り込みに失敗しても、いまのデータでサイトは公開されます。そのときは Actions の実行が最後に赤くなります。
- GitHub の仕様で、公開リポジトリは **60日間なにも更新がないと定期実行が止まります**（お知らせのメールが届きます）。Actions タブから再開できます。
- 手動で取り込むとき：`python update_cats.py --html index.html`
- 公式に新しい地域名が出たときは、位置が「目安」になります。`update_cats.py` の `AREA_POS` に追記すると正確になります。

## 注意
- 写真は自分で撮ったものだけを登録してください。公式の画像は使わない設計です。
- 公式ページの作りが変わって読み取れなくなると、スクリプトは何も書き換えずにエラー終了します。
