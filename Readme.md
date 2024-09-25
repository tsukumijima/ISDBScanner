
# ISDBScanner

![Screenshot](https://github.com/tsukumijima/ISDBScanner/assets/39271166/a60871ed-3fb8-4a6b-9b3e-41a3ccb63362)

**受信可能な日本のテレビチャンネル (ISDB-T/ISDB-S) を全自動でスキャンし、スキャン結果を [EDCB](https://github.com/xtne6f/EDCB) ([EDCB-Wine](https://github.com/tsukumijima/EDCB-Wine))・[Mirakurun](https://github.com/Chinachu/Mirakurun)・[mirakc](https://github.com/mirakc/mirakc) の各設定ファイルや JSON 形式で出力するツールです。**

お使いの Linux PC に接続されているチューナーデバイスを自動的に検出し、全自動で受信可能なすべての地上波・BS・CS チャンネルをスキャンします。  
**実行時に `--exclude-pay-tv` オプションを指定すれば、CS と BS の有料放送をスキャン結果から除外することも可能です。**  
**さらに PC に接続されている対応チューナーを自動的に認識し、Mirakurun / mirakc のチューナー設定ファイルとして出力できます。**

地上波では、13ch 〜 62ch までの物理チャンネルをすべてスキャンして、お住まいの地域で受信可能なチャンネルを検出します。  
BS・CS では、**BS・CS1・CS2 ごとに1つの物理チャンネルのみをスキャンし TS 内のメタデータを解析することで、他のチャンネルスキャンツールよりも高速に現在放送中の衛星チャンネルを検出できます。**

> [!NOTE]  
> 日本のテレビ放送は、主に地上波 (ISDB-T) と衛星放送 (ISDB-S) の2つの方式で行われています。  
> さらに、衛星放送は BS (Broadcasting Satellite) と CS (Communication Satellite) の2つの方式があります。   
> 各放送媒体を区別するため、各媒体には一意なネットワーク ID が割り当てられています。  
>
> 地上波放送では、居住地域によって受信可能な放送局が異なる特性上、放送局ごとにネットワーク ID が割り当てられています。  
> BS 放送では、すべて同じネットワーク ID (0x0004) が割り当てられています。  
> CS 放送では歴史的経緯から、CS1 (0x0006: 旧プラット・ワン系) と CS2 (0x0007: スカイパーフェクTV!2系) で異なるネットワーク ID が割り当てられています。  
> 具体的には、物理チャンネル ND02 / ND08 / ND10 内で放送されているチャンネルは CS1 ネットワーク、それ以外は CS2 ネットワークになります。現在両者の表面的な違いはほとんどありませんが、技術的には異なるネットワークとして扱われています。
>
> BS・CS (衛星放送) では、**同一ネットワークに属するすべてのチャンネルの情報が、放送波の MPEG-2 TS 内の NIT (Network Information Table) や SDT (Service Description Table) というメタデータに含まれています。**  
> そのため、**BS・CS1・CS2 の各ネットワークごとに1つの物理チャンネルをスキャンするだけで、そのネットワークに属するすべてのチャンネルを一括で検出できます。**
> 
> さらに NIT に含まれる「現在放送中の BS/CS 物理チャンネルリスト」の情報を元にチャンネル設定ファイルを出力するため、**将来 BS 帯域再編 (トランスポンダ/スロット移動) が行われた際も、再度 ISDBScanner でチャンネルスキャンを行い、出力されたチャンネル設定ファイルを反映するだけで対応できます。**

> [!NOTE]  
> 地上波の物理チャンネルのうち 53ch - 62ch はすでに廃止されていますが、依然として一部ケーブルテレビのコミュニティチャンネル (自主放送) にて利用されているため、スキャン対象に含めています。

> [!IMPORTANT]  
> 検証環境がないため、ISDB-T の C13 - C63ch (周波数変換パススルー方式) と、ISDB-C (トランスモジュレーション方式) で放送されているチャンネルのスキャンには対応していません。 

- [ISDBScanner](#isdbscanner)
  - [対応チューナー](#対応チューナー)
    - [chardev 版ドライバ](#chardev-版ドライバ)
    - [DVB 版ドライバ](#dvb-版ドライバ)
  - [対応出力フォーマット](#対応出力フォーマット)
  - [インストール](#インストール)
  - [使い方](#使い方)
    - [PC に接続されている利用可能なチューナーのリストを表示](#pc-に接続されている利用可能なチューナーのリストを表示)
    - [チャンネルスキャンを実行](#チャンネルスキャンを実行)
  - [注意事項](#注意事項)
  - [License](#license)

## 対応チューナー

[px4_drv](https://github.com/tsukumijima/px4_drv) / [smsusb (Linux カーネル標準ドライバ)](https://github.com/torvalds/linux/tree/master/drivers/media/usb/siano) 対応チューナー以外での動作は検証していませんが、おそらく動作すると思います。

> [!IMPORTANT]  
> **DVB 版ドライバを利用するには、ISDBScanner v1.1.0 / [recisdb](https://github.com/kazuki0824/recisdb-rs) v1.2.2 以降が必要です。**  
> recisdb v1.2.0 以前のバージョンは DVB 版ドライバの操作に対応していません。

### chardev 版ドライバ

- [px4_drv](https://github.com/tsukumijima/px4_drv)
  - PX-W3U4
  - PX-Q3U4
  - PX-W3PE4
  - PX-Q3PE4
  - PX-W3PE5
  - PX-Q3PE5
  - PX-MLT5PE
  - PX-MLT8PE
  - PX-M1UR
  - PX-S1UR
  - DTV02A-1T1S-U
  - DTV02A-4TS-P
- [pt1_drv](https://github.com/stz2012/recpt1/tree/master/driver)
  - Earthsoft PT1
  - Earthsoft PT2
- [pt3_drv](https://github.com/m-tsudo/pt3)
  - Earthsoft PT3

### DVB 版ドライバ

動作検証は smsusb + VASTDTV VT20 のみ行っています。  
ほかの PX-S1UD 同等品 (Siano SMS2270 採用チューナー) シリーズであれば同様に動作するはずです。

ISDB-T / ISDB-S 対応であれば smsusb 以外のドライバ ([PT1・PT2](https://github.com/torvalds/linux/tree/master/drivers/media/pci/pt1) / [PT3](https://github.com/torvalds/linux/tree/master/drivers/media/pci/pt3) の DVB 版ドライバや [dddvb](https://github.com/DigitalDevices/dddvb) など) でも動作するはずですが、検証はできていません。  

- [smsusb (Linux カーネル標準ドライバ)](https://github.com/torvalds/linux/tree/master/drivers/media/usb/siano)
  - PLEX PX-S1UD
  - PLEX PX-Q1UD
  - MyGica S880i
  - MyGica S270 (PLEX PX-S1UD 同等品)
  - VASTDTV VT20 (PLEX PX-S1UD 同等品)

## 対応出力フォーマット

ISDBScanner は、引数で指定されたディレクトリ以下に複数のファイルを出力します。  
出力されるファイルのフォーマットは以下の通りです。

> [!NOTE]  
> **`--exclude-pay-tv` オプションを指定すると、Channels.json を除き、すべての出力ファイルにおいて有料放送チャンネルの定義が除外されます。**  
> なお、Channels.json に限り、BS 放送のみ常に有料放送チャンネルも含めた結果が出力されます (CS 放送はチャンネルスキャン処理自体が省略されるため出力されない) 。

- **Channels.json**
  - スキャン時に内部的に保持しているトランスポートストリームとサービスの情報を JSON 形式で出力します。
  - 出力される JSON のデータ構造は [constants.py](https://github.com/tsukumijima/ISDBScanner/blob/master/isdb_scanner/constants.py#L8-L77) 内の実装を参照してください。
  - BS/CS の周波数やトランスポンダ番号などかなり詳細な情報が出力されるため、スキャン結果を自作ツールなどで加工したい場合にはこのファイルを利用することをおすすめします。
- **EDCB-Wine**
  - **出力されるファイルはいずれも [EDCB-Wine](https://github.com/tsukumijima/EDCB-Wine) + [Mirakurun](https://github.com/Chinachu/Mirakurun)/[mirakc](https://github.com/mirakc/mirakc) + [BonDriver_mirakc](https://github.com/tkmsst/BonDriver_mirakc) を組み合わせた環境での利用を前提としています。**
  - EDCB のチャンネル設定ファイルには、ChSet4.txt と ChSet5.txt という2つのフォーマットがあります。
    - 両者とも中身は TSV で、各行にチャンネル設定データが記述されています。詳細なフォーマットは [formatter.py](https://github.com/tsukumijima/ISDBScanner/blob/master/isdb_scanner/formatter.py#L105-L266) の実装を参照してください。
    - ChSet4.txt には、ファイル名に対応する BonDriver ”単体” で受信可能なチャンネルの情報が記述されています。
      - **ISDBScanner で生成される ChSet4.txt は BonDriver_mirakc / BonDriver_Mirakurun 専用です。**
      - それ以外の BonDriver で使う際は、別途 ChSet4.txt 内の物理チャンネルの通し番号やチューナー空間番号の対応を変更する必要があります。
    - ChSet5.txt には、EDCB に登録されている BonDriver 全体で受信可能なチャンネルの情報が記述されています。
  - EDCB-Wine (EpgTimerSrv) のチューナー割り当て/チューナー不足判定のロジックが正常に作動しなくなる可能性があるため、**BonDriver_mirakc(_T/_S).dll のチューナー数割り当ては、Mirakurun/mirakc に登録したチューナーの数と種類 (地上波専用/衛星専用/地上波衛星共用) に合わせることを強く推奨します。**
  - **BonDriver_mirakc_T(BonDriver_mirakc).ChSet4.txt**
    - EDCB 用のチャンネル設定ファイルです。EDCB-Wine + Mirakurun/mirakc + BonDriver_mirakc の組み合わせの環境での利用を前提にしています。
    - **地上波のみのチャンネル設定データが含まれます。**
      - 別途 BonDriver_mirakc.dll を BonDriver_mirakc_T.dll にコピーすることで、**BonDriver_mirakc_T.dll を地上波専用の Mirakurun/mirakc 用 BonDriver にすることができます。**
      - PX-W3U4・PX-W3PE4 などの地上波チューナーと衛星チューナーが分かれている機種をお使いの環境では、**EpgTimerSrv のチューナー数設定で Mirakurun/mirakc に登録している地上波チューナーの数だけ BonDriver_mirakc_T.dll に割り当てることで、EDCB 上で地上波チューナーと衛星チューナーを分けて利用できます。**
  - **BonDriver_mirakc_S(BonDriver_mirakc).ChSet4.txt**
    - **BS・CS (衛星放送) のみのチャンネル設定データが含まれます。**
      - 別途 BonDriver_mirakc.dll を BonDriver_mirakc_S.dll にコピーすることで、**BonDriver_mirakc_S.dll を衛星 (BS・CS) 専用の Mirakurun/mirakc 用 BonDriver にすることができます。**
      - PX-W3U4・PX-W3PE4 などの地上波チューナーと衛星チューナーが分かれている機種をお使いの環境では、**EpgTimerSrv のチューナー数設定で Mirakurun/mirakc に登録している衛星チューナーの数だけ BonDriver_mirakc_S.dll に割り当てることで、EDCB 上で地上波チューナーと衛星チューナーを分けて利用できます。**
  - **BonDriver_mirakc(BonDriver_mirakc).ChSet4.txt**
    - **地上波・BS・CS すべてのチャンネル設定データが含まれます。**
      - このチャンネル設定ファイルを合わせて使うことで、**BonDriver_mirakc.dll を地上波・衛星 (BS・CS) 共用の Mirakurun/mirakc 用 BonDriver にすることができます。**
      - PX-MLT5PE などの地上波チューナーと衛星チューナーが統合されている機種 (マルチチューナー) をお使いの環境では、**EpgTimerSrv のチューナー数設定で Mirakurun/mirakc に登録しているマルチチューナーの数だけ BonDriver_mirakc.dll に割り当てることで、EDCB 上で適切にマルチチューナーを利用できます。**
  - **ChSet5.txt**
    - **ChSet4.txt と異なり、登録されている BonDriver のいずれかで受信可能な、地上波・BS・CS すべてのチャンネル設定データが含まれます。**
    - 各チューナー (BonDriver) に依存するチャンネル情報は ChSet4.txt の方に書き込まれます。
- **Mirakurun**
  - **channels.yml**
    - Mirakurun のチャンネル設定ファイルです。地上波・BS・CS すべてのチャンネル設定データが含まれます。
    - **`channel` プロパティに記述されている物理チャンネル名は、[recisdb](https://github.com/kazuki0824/recisdb-rs) が受け入れる物理チャンネル指定フォーマット (T13 ~ T62 / BS01_0 ~ BS23_3 / CS02 ~ CS24) に対応しています。**
      - **recpt1 の物理チャンネル指定フォーマットとは互換性がありません。**
      - recpt1 をチューナーコマンドとして使用している場合は、代わりに channels_recpt1.yml を利用してください。
  - **channels_recpt1.yml**
    - Mirakurun のチャンネル設定ファイルです。地上波・BS・CS すべてのチャンネル設定データが含まれます。
    - **`channel` プロパティに記述されている物理チャンネル名は、[recpt1](https://github.com/stz2012/recpt1) が受け入れる物理チャンネル指定フォーマット (13 ~ 62 / BS01_0 ~ BS23_3 / CS2 ~ CS24) に対応しています。**
      - **recisdb の物理チャンネル指定フォーマットとは互換性がありません。**
      - recisdb をチューナーコマンドとして使用している場合は、代わりに channels.yml を利用してください。
  - **tuners.yml**
    - Mirakurun のチューナー設定ファイルです。
    - ISDBScanner で自動検出された、PC に接続されているすべてのチューナーの情報が含まれます。
    - **`command` プロパティに記述されているチューナーコマンドには、[recisdb](https://github.com/kazuki0824/recisdb-rs) の `tune` サブコマンドが設定されています。**
      - recpt1 をチューナーコマンドとして使用している場合は、代わりに tuners_recpt1.yml を利用してください。
  - **tuners_recpt1.yml**
    - Mirakurun のチューナー設定ファイルです。
    - ISDBScanner で自動検出された、PC に接続されているすべてのチューナーの情報が含まれます。
    - **`command` プロパティに記述されているチューナーコマンドには、[recpt1](https://github.com/stz2012/recpt1) コマンドが設定されています。**
      - recisdb をチューナーコマンドとして使用している場合は、代わりに tuners.yml を利用してください。
      - recpt1 に加え、`decoder` として arib-b25-stream-test コマンドが導入されていることを前提としています。
      - recisdb と異なり recpt1 は DVB 版ドライバに対応していないため、DVB デバイスは記述から除外されます。
- **mirakc**
  - **config.yml**
    - mirakc の設定ファイルです。
    - `channels` セクションには、地上波・BS・CS すべてのチャンネル設定データが含まれます。
      - **`channel` プロパティに記述されている物理チャンネル名は、[recisdb](https://github.com/kazuki0824/recisdb-rs) が受け入れる物理チャンネル指定フォーマット (T13 ~ T62 / BS01_0 ~ BS23_3 / CS02 ~ CS24) に対応しています。**
        - **recpt1 の物理チャンネル指定フォーマットとは互換性がありません。**
        - recpt1 をチューナーコマンドとして使用している場合は、代わりに config_recpt1.yml を利用してください。
    - `tuners` セクションには、ISDBScanner で自動検出された、PC に接続されているすべてのチューナーの情報が含まれます。
      - **`command` プロパティに記述されているチューナーコマンドには、[recisdb](https://github.com/kazuki0824/recisdb-rs) の `tune` サブコマンドが設定されています。**
        - recpt1 をチューナーコマンドとして使用している場合は、代わりに config_recpt1.yml を利用してください。
  - **config_recpt1.yml**
    - mirakc の設定ファイルです。
    - `channels` セクションには、地上波・BS・CS すべてのチャンネル設定データが含まれます。
      - **`channel` プロパティに記述されている物理チャンネル名は、[recpt1](https://github.com/stz2012/recpt1) が受け入れる物理チャンネル指定フォーマット (13 ~ 62 / BS01_0 ~ BS23_3 / CS2 ~ CS24) に対応しています。**
        - **recisdb の物理チャンネル指定フォーマットとは互換性がありません。**
        - recisdb をチューナーコマンドとして使用している場合は、代わりに config.yml を利用してください。
    - `tuners` セクションには、ISDBScanner で自動検出された、PC に接続されているすべてのチューナーの情報が含まれます。
      - **`command` プロパティに記述されているチューナーコマンドには、[recpt1](https://github.com/stz2012/recpt1) コマンドが設定されています。**
        - recisdb をチューナーコマンドとして使用している場合は、代わりに config.yml を利用してください。
      - recpt1 に加え、`decode-filter` として arib-b25-stream-test コマンドが導入されていることを前提としています。
      - recisdb と異なり recpt1 は DVB 版ドライバに対応していないため、DVB デバイスは記述から除外されます。

## インストール

ISDBScanner は、チューナー受信コマンドとして [recisdb](https://github.com/kazuki0824/recisdb-rs) を利用しています。  
そのため、事前に recisdb のインストールが必要です。

> [!NOTE]  
> **[recisdb](https://github.com/kazuki0824/recisdb-rs) は、旧来から chardev 版ドライバ用チューナー受信コマンドとして利用されてきた [recpt1](https://github.com/stz2012/recpt1) と、標準入出力経由で B25 デコードを行う [arib-b25-stream-test](https://www.npmjs.com/package/arib-b25-stream-test) / [b25 (libaribb25 同梱)](https://github.com/tsukumijima/libaribb25) のモダンな代替として開発された、次世代の Rust 製チューナー受信コマンドです。**  
> 
> チューナーからの放送波の受信と B25 デコード、さらに信号レベルの確認 (checksignal) をすべて recisdb ひとつで行えます。  
> さらに recpt1 と異なり BS の物理チャンネルがハードコードされていないため、**将来 BS 帯域再編 (トランスポンダ/スロット移動) が行われた際も、recisdb を更新することなく ISDBScanner でのチャンネルスキャンと各設定ファイルの更新だけで対応できます。**

以下の手順で、recisdb をインストールしてください。  
下記は recisdb v1.2.2 時点でのインストール手順です。 

```bash
# Deb パッケージは Ubuntu 20.04 LTS / Debian 11 以降に対応

# x86_64 環境
wget https://github.com/kazuki0824/recisdb-rs/releases/download/1.2.2/recisdb_1.2.2-1_amd64.deb
sudo apt install ./recisdb_1.2.2-1_amd64.deb
rm ./recisdb_1.2.2-1_amd64.deb

# arm64 環境
wget https://github.com/kazuki0824/recisdb-rs/releases/download/1.2.2/recisdb_1.2.2-1_arm64.deb
sudo apt install ./recisdb_1.2.2-1_arm64.deb
rm ./recisdb_1.2.2-1_arm64.deb
```
> [!NOTE]  
> アンインストールは `sudo apt remove recisdb` で行えます。

ISDBScanner 自体は Python スクリプトですが、Python 3.11 がインストールされていない環境でも動かせるよう、PyInstaller でシングルバイナリ化した実行ファイルを公開しています。  
下記は ISDBScanner v1.1.6 時点でのインストール手順です。

```bash
# x86_64 環境
sudo wget https://github.com/tsukumijima/ISDBScanner/releases/download/v1.1.6/isdb-scanner -O /usr/local/bin/isdb-scanner
sudo chmod +x /usr/local/bin/isdb-scanner

# arm64 環境
sudo wget https://github.com/tsukumijima/ISDBScanner/releases/download/v1.1.6/isdb-scanner-arm -O /usr/local/bin/isdb-scanner
sudo chmod +x /usr/local/bin/isdb-scanner
```

## 使い方

![Screenshot](https://github.com/user-attachments/assets/ff759d35-b902-47f6-aeb4-18e5949bee30)

ISDBScanner は、引数で指定されたディレクトリ (デフォルト: `./scanned/`) 以下に複数のファイルを出力します。  
出力される各ファイルのフォーマットは [対応出力フォーマット](#対応出力フォーマット) を参照してください。

> [!TIP]
> ISDBScanner v1.2.0 以降では、`--lnb` オプションを指定すると、衛星放送受信時にチューナーからアンテナに給電できます（動作未確認）。  
> `--lnb 11v` と `--lnb 15v` の両方を指定できますが、px4_drv 対応チューナーには `--lnb 15v` のみ指定できます。  
> 明示的に LNB 給電を無効化するには、`--lnb low` を指定します。何も指定されなかったときは LNB 給電を行いません。

### PC に接続されている利用可能なチューナーのリストを表示

![Screenshot](https://github.com/tsukumijima/ISDBScanner/assets/39271166/99a9fcd4-0afb-4c42-914a-d284fb3cf057)

`isdb-scanner --list-tuners` と実行すると、PC に接続されている、利用可能なチューナーのリストが表示されます。  
チューナーが現在使用中の場合、チューナー情報の横に `(Busy)` と表示されます。

PC に接続したはずのチューナーが認識されていない場合は、チューナードライバのインストール・ロード状態や、チューナーとの物理的な接続状況を確認してみてください。

> [!NOTE]  
> チューナーは chardev 版デバイスが先に認識され、DVB 版デバイスは後に認識されます。  
> chardev 版デバイスと DVB 版デバイスが同時に接続されている場合、chardev 版デバイスの方を優先してチャンネルスキャンに使用します。

### チャンネルスキャンを実行

地上波・BS・CS すべてのチャンネルをスキャンする際は、`isdb-scanner` と実行してください。  
出力先ディレクトリを指定しない場合は `./scanned/` に出力されます。  

地上波と BS の無料放送のみをスキャン結果に含めたい場合は、`isdb-scanner --exclude-pay-tv` と実行してください。

<img align="center" width="49%" src="https://github.com/tsukumijima/ISDBScanner/assets/39271166/d54dd1c9-0ad8-40a0-9678-60f5a1ea8fc6">
<img align="center" width="49%" src="https://github.com/tsukumijima/ISDBScanner/assets/39271166/59368ddb-38b4-40fe-9c7f-7aee39828d13">
<br><br>

**チャンネルスキャン中は、検出されたトランスポートストリーム / チャンネル (サービス) のリストとスキャンの進捗状況が、リアルタイムでグラフィカルに表示されます。**  
チャンネルスキャンに使おうとしたチューナーが現在使用中の際は、自動的に空いているチューナーを選択してスキャンを行います。  
もし地上波で特定のチャンネルが受信できていない場合は、停波中でないかや受信状態などを確認してみてください。

なお、チャンネルスキャンには地デジ・BS・CS のフルスキャンを行う場合で 6 分程度、地デジ・BS の無料放送のみをスキャンする場合で 5 分半程度かかります。  
コマンドを実行した後は終わるまで放置しておくのがおすすめです。

> [!IMPORTANT]  
> **地上波で複数の中継局の電波を受信できる地域にお住まいの場合、同一のチャンネルが重複して検出されることがあります。**  
> この場合、ISDBScanner は同一のチャンネルを放送している各物理チャンネルごとに信号レベルを計測し、最も受信状態の良い物理チャンネルのみを選択します。動作確認はできていないけどおそらく動くはず…？  

> [!NOTE]  
> 出力される Mirakurun / mirakc のチューナー設定ファイルには、現在 PC に接続中のチューナーのみが記載されます。  
> 接続しているはずのチューナーが記載されない (ISDBScanner で認識されていない) 場合は、カーネルドライバのロード状態や、物理的なチューナーの接続状態を確認してみてください。

## 注意事項

- **すでに Mirakurun / mirakc を導入している環境でチャンネルスキャンを行う際は、できるだけ Mirakurun / mirakc を停止してから行ってください。**
  - ISDBScanner は Mirakurun / mirakc を経由せず、recisdb を通してダイレクトにチューナーデバイスにアクセスします。  
    **チャンネルスキャンと Mirakurun / mirakc による EPG 更新や録画のタイミングが重なると、チューナー数次第ではチューナーが不足してスキャンに失敗する可能性があります。**
  - 録画中でないことを確認の上一旦 Mirakurun / mirakc サービスを停止し、ほかのソフトにチューナーを横取りされない状況でスキャンすることをおすすめします。  
    スキャン完了後は停止した Mirakurun / mirakc サービスの再開を忘れずに。
- **EDCB-Wine のチャンネル設定ファイルを実稼働環境に反映する場合は、EDCB-Wine で利用している Mirakurun / mirakc のチャンネル設定ファイルも、必ず同時に更新してください。**
  - BonDriver は物理チャンネル自体の数値ではなく基本 0 からの連番となる「通し番号」でチャンネル切り替えを行う仕様になっていて、ChSet4.txt にはこの通し番号が記載されています。
    - EDCB-Wine で利用している BonDriver_mirakc の場合、Mirakurun / mirakc 側で登録した物理チャンネルの配列インデックスがそのまま「通し番号」になります。
  - つまり、**Mirakurun / mirakc のチャンネル設定ファイルを変更して登録中の物理チャンネルを増減させると、この BonDriver の「通し番号」がズレてしまい、再度 ChSet4.txt を生成し直さない限り正しくチャンネル切り替えが行えない状態に陥ります。**
    - 実際私はこれが原因で録画に失敗したことがあります…。
    - こうした事態を避けるため、**EDCB-Wine と Mirakurun / mirakc のチャンネル設定ファイルは、片方だけを更新するのではなく、常に両方を同時に更新するようにしてください。**
- **深夜にチャンネルスキャンを行うと、停波中のチャンネルがスキャン結果から漏れてしまいます。**
  - 特に NHK Eテレは毎日深夜に放送を休止しているため、深夜にスキャンを行うとスキャン結果から漏れてしまいます。
  - できるだけ (停波中のチャンネルがない) 日中時間帯でのチャンネルスキャンをおすすめします。

## License

[MIT License](License.txt)
