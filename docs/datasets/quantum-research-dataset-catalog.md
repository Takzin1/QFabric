# Quantum Research Dataset Catalog — QFabric

> **調査日:** 2026-10-18 (JST)  
> **Status:** `candidate / metadata-reviewed` — **候補リンクの原典確認のみ**。原ファイルのダウンロード、SHA-256計算、列・単位監査、利用許諾の個別確認、NotebookLM投入、QFabricへの数値取り込みは **未実施**。  
> **Scope:** 量子計算・量子誤り訂正（QEC）・単一ショット読み出し・量子制御の公開論文／データ。CrystalTwinAIの晶析データとは混合しない。

この台帳は、公開論文の文献解釈を **NotebookLM（現在の製品名: Gemini Notebook）** で整理し、研究データの **正本（原ファイル）** を独立した検証レイヤーで管理するための候補一覧。リンクが公開されていることは再配布許諾や装置互換性を意味しない。

## 1. 優先順位つき一覧

| ID | 優先 | 論文・公開データ | 年 | データ種別 | 公開形式・概算容量 | QFabricへの想定用途 | 取り込み状態 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| QRD-001 | **P0** | [Caune et al., *Demonstrating real-time and low-latency quantum error correction with superconducting qubits*](https://arxiv.org/abs/2410.05202) / [Zenodo v1](https://zenodo.org/records/13961130) / [Zenodo v2](https://zenodo.org/records/15364358) | 2024（v2: 2025） | **実機由来** | CSV / TXT / HDF5、v2全体約 **1.2 GB**。小ファイルあり | FPGAデコード遅延、readout/feedback参照、証拠管理 | metadata-reviewed; raw-not-fetched |
| QRD-002 | **P1** | [Stein, *Calibration-Conditioned FiLM Decoders…*](https://arxiv.org/abs/2601.16123) / [Zenodo](https://zenodo.org/records/20768087) | 2026 | **IBM Quantum実機由来** | TAR.GZ内JSON・OpenQASM、README、約 **145.7 MB** | T1/T2、較正履歴、測定ビット列の来歴管理 | metadata-reviewed; raw-not-fetched |
| QRD-003 | **P2** | [Gunyho et al., *Single-Shot Readout of a Superconducting Qubit Using a Thermal Detector*](https://doi.org/10.1038/s41928-024-01147-7) / [arXiv](https://arxiv.org/abs/2303.03668) / [Zenodo](https://zenodo.org/records/10000511) | 2023データ／2024論文 | **実機実験由来** | ZIP、約 **922.9 MB**（内部形式は未調査） | 単一ショット読み出し解析の比較候補 | metadata-reviewed; raw-not-fetched |
| QRD-004 | **P3** | [Perrier, Youssry & Ferrie, *QDataSet*](https://doi.org/10.1038/s41597-022-01639-1) / [GitHub](https://github.com/eperrier/QDataSet) / [ソフトウェアDOI](https://doi.org/10.5281/zenodo.5202814) | 2022 | **数値シミュレーション** | 大規模圧縮データ（論文記載で合計約 **14 TB**）、生成コード・notebooks | 制御パルス、ノイズ・量子状態ベンチマーク | metadata-reviewed; subset availability unverified |

**重要:** QRD-001～003は実機由来だが、QFabricが当該装置を実行・読み出し可能という意味ではない。QRD-004は「実験で測定した値」ではなくシミュレーション生成値である。

## 2. 個別調査票

### QRD-001 — Real-time/low-latency quantum error correction

- **著者:** Laura Caune, Luka Skoric, Nick S. Blunt ほか（原典参照）
- **論文:** https://arxiv.org/abs/2410.05202
- **論文DOI:** https://doi.org/10.48550/arXiv.2410.05202
- **データv1:** https://doi.org/10.5281/zenodo.13961130
- **データv2:** https://zenodo.org/records/15364358 （最新として原ページからリンク。v1と区別してバージョン固定）
- **実験系:** 超伝導プロセッサ（Ankaa-2）＋ FPGAベースのQECデコーダ
- **原典が説明する観測項目:** hard/soft measurements、decoder shot results、logical-error probabilities、FPGA decoder/feedback timings、T1用遅延、measurement fidelity。
- **最初に読む小容量ファイル:** `fig4b_decoding_response_time.csv`（917 B）、`figS4d_t1_time_fitting.csv`（378 B）、`figS4c_feedback_response_time_probability_density_data.csv`（13.9 kB）。raw候補 `fast_feedback_raw_data.h5`（5.6 MB）。
- **単位:** CSV列ヘッダ・README/論文の図表で照合 **未実施**。たとえばタイミング値を自動的に `µs` と決めつけない。
- **ライセンス:** **未確認**（Zenodoページの権利欄にライセンス識別子を確認できず）。再配布・同梱前に公式メタデータを確認。
- **留意:** v2には `stability_9_raw_data.h5`（130.2 MB）等が増えている。小さいCSVまたは5.6 MBのHDF5で先行検証。
- **QFabric候補:** 実測遅延の `measurement_metadata`、ソースバージョン、測定手法、原ファイルのハッシュ。QICK readoutを実行した証拠として扱わない。

### QRD-002 — Calibration-conditioned decoding on IBM Quantum

- **著者:** Samuel Stein（公開データレコード）
- **論文:** https://arxiv.org/abs/2601.16123
- **公開データ:** https://doi.org/10.5281/zenodo.20768087
- **原著者のコード候補:** https://github.com/Samuelstein1224/calibration-conditioned-decoding
- **実験系:** `ibm_kingston`, `ibm_pittsburgh`, `ibm_fez` の **352 hardware snapshots**（Zenodoの記載）。
- **形式・項目:** `ibm_fez.tar.gz`（9.0 MB）、`ibm_kingston.tar.gz`（71.4 MB）、`ibm_pittsburgh.tar.gz`（65.3 MB）。展開後の `info.json`、`calibration.json`（T1・T2・gate/readout error）、`circuit_state0.qasm` / `circuit_state1.qasm`、`bitstrings.json`。付属の `README.md` にスキーマ説明。
- **推奨開始点:** 最小アーカイブ `ibm_fez.tar.gz` と公開README。安全な展開処理（パストラバーサル対策、展開サイズ上限）を用いる。
- **単位・較正時刻:** `calibration.json` の値と論文記述を照合 **未実施**。一意のハードウェアジョブIDは公開データ側で匿名化されているため、生成・推定しない。
- **ライセンス:** **未確認**。再配布前に権利表記の確認が必須。
- **QFabric候補:** `CalibrationRecord` に直結させず、まず `external_calibration_evidence` に出典・基準時刻・測定法を保持。IBM Quantum SDK出力をQICKデバイス較正と誤認しない。

### QRD-003 — Thermal-detector single-shot superconducting-qubit readout

- **著者:** Andras Marton Gunyho, Suman Kundu, Jian Ma ほか
- **論文:** https://doi.org/10.1038/s41928-024-01147-7
- **プレプリント:** https://arxiv.org/abs/2303.03668
- **公開データ:** https://doi.org/10.5281/zenodo.10000511
- **公開レコード:** Zenodo v2（2023-10-13公開、2024-04-24更新）。
- **形式:** `data-for-single-shot-readout-of-a-superconducting-qubit-using-a-thermal-detector.zip`、約922.9 MB。
- **内容:** 論文の図を生成するためのデータ・解析コード。各変数の詳細、内部形式、量・単位、校正ファイルは **ZIP内部未調査**。
- **ライセンス:** **未確認**。
- **QFabric候補:** 単一ショット readout evidence の研究。詳細フィールドはREADME・生データの検査後に確定する。検証前に `single-shot fidelity` 等の結果を生成しない。

### QRD-004 — QDataSet: quantum datasets for machine learning

- **著者:** Elija Perrier, Akram Youssry, Chris Ferrie
- **査読論文:** https://doi.org/10.1038/s41597-022-01639-1
- **論文（PMC全文）:** https://pmc.ncbi.nlm.nih.gov/articles/PMC9508231/
- **開発コード・サンプル:** https://github.com/eperrier/QDataSet
- **ソフトウェアDOI:** https://doi.org/10.5281/zenodo.5202814
- **データ種別:** **シミュレーション（NOT measured）**。1–2量子ビットの状態、Hamiltonian、制御パルス列、ノイズ・歪み・時系列等。
- **規模:** 52データセット、論文記載の圧縮総量は約14 TB。NotebookLMに全量投入しない。GitHub内の `examples/` / `simulation/` からサンプルや生成コードを選定。
- **ライセンス:** GitHubのコードはMIT表記、論文本文はCC BY 4.0。**各データファイルのライセンス／配布元の可用性は個別に要確認**。コードのMITをすべてのデータのライセンスと同一視しない。
- **QFabric候補:** synthetic control pulse/measurement-like outputを扱う解析パイプライン、単位系・ノイズ定義の検証。実機QICKの性能を示すデータとして使わない。
- **留意:** READMEの外部データ配布先リンクは利用可能性 **未確認**。14 TBをダウンロードしない。

## 3. NotebookLM（Gemini Notebook）の役割と投入手順

> 公式: [Gemini Notebook製品ページ](https://workspace.google.com/intl/en_SD/products/gemini-notebook/) / [Data Tables](https://workspaceupdates.googleblog.com/2025/12/transform-sources-structured-data-tables-notebooklm.html) / [構造化形式の公式案内](https://blog.google/innovation-and-ai/products/notebooklm/better-research-notebooklm/)

1. **論文PDF** と Zenodoの**README・Description・データ辞書**を、出典を明示した別々のソースとして投入する。
2. 「実験装置」「測定対象」「実行条件」「測定単位」「誤差・不確かさ」「図番号・ページ番号」「データファイルへの対応」を、根拠箇所付きの表に整理させる。
3. Data Tables → Google Sheets、または利用可能ならCSV/JSONへエクスポートする。機能提供状況はアカウントによる。
4. **NotebookLMの表は `unverified_extraction`。** ページ・図・データ辞書を人間が照合するまで `verified` にしない。
5. **数値の正本は元のCSV/HDF5/JSONファイル**。NotebookLMに測定値を推測・補間・補正させない。図の読み取り値は `figure_digitized` として実測CSVと区別。
6. Gemini Notebookによる解釈と原ファイルの数値を分離して保管。HDF5/大容量ZIPの展開・解析はPython側で実行する。

### NotebookLM用の文献構造化プロンプト（案）

~~~text
対象論文と付随する公開データ説明を引用箇所つきで分析してください。
以下を列に持つ表を作成:
paper_title, paper_doi, dataset_doi, dataset_version, author,
hardware_family, device_name, observable, original_unit,
measurement_method, acquisition_conditions, calibration_details,
uncertainty, dataset_filename, source_locator, data_kind,
license_claim, extraction_confidence, verification_status。

- 不明は null / 未確認 とし、推測で埋めない。
- 実機測定/measured、物理モデルのsimulation、人工syntheticを明確に区別。
- 可能なら論文ページ、図、表、補足資料の識別子を示す。
- Zenodoのデータと論文記述が矛盾する場合は両方を記録。
- 「NotebookLMによる抽出結果」であることを明示し、
  生データファイルを解析したかのように説明しない。
~~~

## 4. QFabric向けデータ契約（提案、未実装）

**現行v0.7の `qfabric-research-proposal/1` や `qfabric-crystaltwin-report/1` を書き換えない。** データセットの専用エンベロープを将来追加する。以下のJSONは項目案であって取得済みデータではない。

~~~json
{
  "schemaVersion": "qfabric-quantum-dataset-evidence/1",
  "datasetId": "QRD-001",
  "paperDoi": "10.48550/arXiv.2410.05202",
  "datasetRecordUrl": "https://zenodo.org/records/15364358",
  "datasetVersion": "v2",
  "filename": "fig4b_decoding_response_time.csv",
  "rawFileSha256": null,
  "licenseIdentifier": null,
  "provenance": "measured",
  "provenanceVerification": "record_only",
  "units": null,
  "observable": null,
  "sourceLocator": null,
  "notebookExtractionStatus": "not_started",
  "validationStatus": "candidate",
  "hardwareCompatibility": "unverified"
}
~~~

### Ingest時に必要なゲート

- [ ] DOI、文献タイトル、バージョン、データ公開URLを確定し原典を保存
- [ ] 権利情報、商用利用・改変・再配布許諾を**ファイル別**に確認
- [ ] HTTPSを使いサイズ上限・タイムアウト・リダイレクト先を制限、無条件の外部URL取得を避ける
- [ ] 元ファイルを変更せずSHA-256を計算・保存し、配布元チェックサムも照合
- [ ] CSV/HDF5/JSONを形式別パーサで読み取り、数値・単位・欠損・次元・時刻原点を検査
- [ ] ZIP/TARは展開先・展開後容量を制限し、未知のコードやpickleを実行しない
- [ ] `measured` / `simulation` / `synthetic` / `figure_digitized` を混同しない
- [ ] NotebookLM由来の抽出には引用箇所・抽出方法・人間による照合状況を付与
- [ ] 未照合は `quarantined`、検証済みのみ `accepted`、不正入力は `rejected`
- [ ] QICKプログラムやRFSoCにデータを送らない。外部実験データ≠ローカル実機互換性

## 5. 実装順序

1. **P0** QRD-001の小容量CSV（917 B）を取得・形式確認し、原典リンク・SHA-256・単位・論文図との対応をチェック。
2. QRD-001の5.6 MB HDF5で読み出し用データ構造と較正参照を監査。実機データだが装置上で再実行はしない。
3. **P1** QRD-002の `ibm_fez.tar.gz` とREADMEを安全に展開し、校正JSON／測定ビット列／回路構造をレジストリに登録。
4. **P2** QRD-003は容量とライセンス確認後に部分導入。
5. **P3** QRD-004は制御パルスの小規模シミュレーションサンプル／生成コードを利用し、実測ベンチマークから分離。
6. NotebookLMの引用付き表と **原データの独立した数値パーサ** の結果を突合し、差分・不明項目をEvidence Registryへ残す。
7. 再現手順と拒否ケースをCIに入れた後、Nemotronからの仮説提案に**確認済みの出典**だけを参照させる。

## 6. 論文・サービスの公式参照リンク

| 区分 | URL |
| --- | --- |
| Caune論文 | https://arxiv.org/abs/2410.05202 |
| Cauneデータv1 DOI | https://doi.org/10.5281/zenodo.13961130 |
| Cauneデータv2レコード | https://zenodo.org/records/15364358 |
| Stein論文 | https://arxiv.org/abs/2601.16123 |
| SteinデータDOI | https://doi.org/10.5281/zenodo.20768087 |
| Gunyho論文DOI | https://doi.org/10.1038/s41928-024-01147-7 |
| GunyhoデータDOI | https://doi.org/10.5281/zenodo.10000511 |
| Perrierほか（Scientific Data） | https://doi.org/10.1038/s41597-022-01639-1 |
| QDataSet GitHub | https://github.com/eperrier/QDataSet |
| QDataSetコードDOI | https://doi.org/10.5281/zenodo.5202814 |
| Gemini Notebook公式 | https://workspace.google.com/intl/en_SD/products/gemini-notebook/ |
| Data Tables公式 | https://workspaceupdates.googleblog.com/2025/12/transform-sources-structured-data-tables-notebooklm.html |

### 変更履歴

- **2026-10-18:** 初回候補4件。論文/記録のリンク・公開ファイル概要を公式ページと照合。原データ未取得のためSHA-256・単位・ライセンス・ファイル内容を未確認と明示。
