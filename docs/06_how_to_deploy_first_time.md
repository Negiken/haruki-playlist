# はじめて公開する人向けの手順

最終更新：2026-11-11

最初の 1 回だけ、GitHub と AWS をつなぐ設定を手作業で行う。終われば、以降は `main` に push するだけで自動的に公開される。所要時間は 30 分ほど。

> **この手順を進めると AWS の課金が始まる**（目安は §6）。やめたくなったら §7 で全部消せる。

---

## 0. 用意するもの

| もの | 備考 |
|---|---|
| GitHub アカウント | リポジトリは非公開（Private）でよい |
| AWS アカウント | 管理者権限でログインできること |
| AWS CLI | この PC には導入済み。認証が未設定なので §2 で設定する |
| Anthropic の API キー | https://console.anthropic.com で発行。無くても公開はできる（キーワード方式で動く） |

---

## 1. GitHub にリポジトリを作って push する

1. GitHub で空のリポジトリを作る（例：`haruki-playlist`）。README などは追加しない
2. このフォルダで：

   ```powershell
   git init -b main
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/<ユーザー名>/haruki-playlist.git
   ```

3. **まだ push しない**（先に §2〜3 を済ませないと、最初のデプロイが認証エラーで失敗する。失敗しても害はなく、後で再実行できる）

---

## 2. AWS CLI にログインする

```powershell
aws login
aws configure set region ap-northeast-1
aws sts get-caller-identity
```

最後のコマンドでアカウント ID が表示されれば成功。

---

## 3. GitHub 用のロールを作る（1 回だけ）

```powershell
aws cloudformation deploy `
  --stack-name haruki-playlist-bootstrap `
  --template-file infra/bootstrap.yml `
  --capabilities CAPABILITY_NAMED_IAM `
  --parameter-overrides GitHubOwner=<ユーザー名> GitHubRepo=haruki-playlist
```

> `EntityAlreadyExists … token.actions.githubusercontent.com` というエラーになったら、このアカウントには既に GitHub の OIDC プロバイダーがある。末尾に `CreateOidcProvider=false` を足してもう一度実行する。

作られたロールの ARN を表示する：

```powershell
aws cloudformation describe-stacks --stack-name haruki-playlist-bootstrap `
  --query "Stacks[0].Outputs[0].OutputValue" --output text
```

`arn:aws:iam::123456789012:role/haruki-playlist-github-deploy` のような文字列が出るので控える。

---

## 4. GitHub に値を登録して push する

リポジトリの **Settings → Secrets and variables → Actions** を開く。

| タブ | 名前 | 値 |
|---|---|---|
| Variables | `AWS_DEPLOY_ROLE_ARN` | §3 で控えた ARN |
| Secrets | `ANTHROPIC_API_KEY` | Anthropic の API キー（省略可） |

登録したら push する：

```powershell
git push -u origin main
```

リポジトリの **Actions** タブで「Deploy」が動き出す。初回は CloudFront の作成に時間がかかり、**10〜15 分**ほどで終わる。

終わると、実行結果の Summary に公開 URL（`https://xxxxxxxx.cloudfront.net`）が表示される。これを知り合いに共有すればよい。

URL を後から調べるには：

```powershell
aws cloudformation describe-stacks --stack-name haruki-playlist `
  --query "Stacks[0].Outputs[?OutputKey=='SiteUrl'].OutputValue" --output text
```

公開できたら `05_test_checklist.md` の「公開後の確認」を行う。

---

## 5. うまくいかないとき

| 症状（Actions のどのステップか） | 原因と対処 |
|---|---|
| 「AWS 認証」で `Not authorized to perform sts:AssumeRoleWithWebIdentity` | ロールの条件と、GitHub が送ってくる識別子が一致していない。下の「GitHub が送っている識別子を調べる」で実際の値を確認し、§3 のパラメータ（`GitHubOwner` / `GitHubRepo`、大文字小文字も区別）を合わせて再実行する。`main` 以外のブランチから実行した場合もこうなる |
| 「AWS 認証」で `Could not load credentials from any providers` | `AWS_DEPLOY_ROLE_ARN` がワークフローから見えていない。Secrets 側や「Environment variables」に登録していないか確認し、**Variables タブの「Repository variables」**に登録する |
| 「インフラを適用」で失敗 | AWS コンソールの CloudFormation → `haruki-playlist` → イベントで、最初に失敗したリソースの理由を見る。既定 VPC が無いアカウントでは失敗する（03 §9） |
| 初回の適用に失敗して、再実行しても `ROLLBACK_COMPLETE` で進まない | 作りかけのスタックを消してから再実行：`aws cloudformation delete-stack --stack-name haruki-playlist` |
| 「EC2 上で配置・再起動」で失敗 | そのステップのログに EC2 側の出力（アプリの起動ログを含む）が出ている。前の版があれば自動で戻っている |
| 「公開URLで動作確認」で失敗 | 数分待って Actions の「Re-run jobs」。続く場合は下のログ確認へ |
| 画面は出るが、ずっと「キーワードで選曲」 | `ANTHROPIC_API_KEY` が未登録か無効。登録し直して Actions の「Run workflow」で再デプロイ。サーバーのログも確認する |

### GitHub が送っている識別子を調べる

GitHub の識別子は `repo:<ユーザー名>@<ユーザーID>/<リポジトリ名>@<リポジトリID>:ref:refs/heads/main` の形をしている。失敗した引き受けは CloudTrail に残るので、実際の値を確認できる（反映まで数分かかることがある）：

```powershell
aws cloudtrail lookup-events --region ap-northeast-1 --max-results 1 `
  --lookup-attributes AttributeKey=EventName,AttributeValue=AssumeRoleWithWebIdentity `
  --query "Events[0].Username" --output text
```

ID まで固定したい場合は、§3 のコマンドの `--parameter-overrides` に `GitHubOwnerId=<ユーザーID> GitHubRepoId=<リポジトリID>` を足す（省略時はどの ID でも一致する）。

### サーバーのログを見る

SSH は開けていない。AWS コンソールの **EC2 → インスタンス `haruki-playlist` → 接続 → セッションマネージャー** でシェルに入り：

```bash
sudo journalctl -u haruki-playlist -n 100 --no-pager     # 直近のログ
sudo journalctl -u haruki-playlist -f                     # 流し見
sudo systemctl status haruki-playlist
```

Claude を呼ぶたびに `claude usage: …` の行が出る。失敗時は `Claude 解析に失敗。ルールベースに切り替えます` と理由が出る。

---

## 6. 費用の目安（東京リージョン・月額）

| 項目 | 目安 |
|---|---|
| EC2 `t4g.micro`（常時稼働） | 約 8 ドル |
| EBS 8GB | 約 1 ドル |
| Elastic IP（パブリック IPv4） | 約 4 ドル |
| CloudFront・S3・Parameter Store | 数人利用ならほぼ 0 |
| Claude API（Haiku） | 1 回あたり 0.3 円前後の見積もり（実測ではない）。数人利用なら月数十〜数百円、1 日の上限（300 回）まで毎日使い切っても月 3,000 円以内 |

合計で**月 13 ドル前後**。金額は変わることがあるので、AWS の請求ダッシュボードで実額を確認し、予算アラート（AWS Budgets）を設定しておくと安心。

使わない期間は EC2 を「停止」すれば EC2 の料金は止まる（Elastic IP と EBS の分は残る）。再開は「開始」するだけで、URL は変わらない。

---

## 7. 日々の運用

| やりたいこと | 方法 |
|---|---|
| 変更を公開する | `main` に push する（またはプルリクエストをマージする） |
| 変更なしで再デプロイ | Actions → Deploy → Run workflow |
| 前の版に戻す | `git revert <コミット>` して push |
| API キーを替える | GitHub の Secret を更新して Run workflow |
| 上限値を変える | `backend/app/config.py` の既定値を変えて push |
| 一時的に Claude を止める | Secret `ANTHROPIC_API_KEY` を削除し、AWS の Parameter Store から `/haruki-playlist/anthropic-api-key` を削除して Run workflow |

### 全部消す

```powershell
# バケットを空にする（空でないとスタックを消せない）
$bucket = aws cloudformation describe-stacks --stack-name haruki-playlist `
  --query "Stacks[0].Outputs[?OutputKey=='ArtifactBucketName'].OutputValue" --output text
aws s3 rm "s3://$bucket" --recursive

aws cloudformation delete-stack --stack-name haruki-playlist
aws cloudformation wait stack-delete-complete --stack-name haruki-playlist
aws ssm delete-parameter --name /haruki-playlist/anthropic-api-key
aws cloudformation delete-stack --stack-name haruki-playlist-bootstrap
```

CloudFront の削除に 10 分以上かかることがある。
