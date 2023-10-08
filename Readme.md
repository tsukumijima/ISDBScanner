
# ISDBScanner

![Screenshot](https://github.com/tsukumijima/ISDBScanner/assets/39271166/e5f10b66-58de-486a-aa4c-e65945435602)

**受信可能な日本のテレビチャンネル (ISDB-T/ISDB-S) を全自動でスキャンし、スキャン結果を [EDCB](https://github.com/xtne6f/EDCB) ([EDCB-Wine](https://github.com/tsukumijima/EDCB-Wine))・[Mirakurun](https://github.com/Chinachu/Mirakurun)・[mirakc](https://github.com/mirakc/mirakc) の各設定ファイルや JSON 形式で出力するツールです。**

お使いの Linux PC に接続されているチューナーデバイスを自動的に検出し、全自動で受信可能なすべての地上波・BS・CS チャンネルをスキャンします。  
**実行時に `--exclude-pay-tv` オプションを指定すれば、CS と BS の有料放送をスキャン結果から除外することも可能です。**

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
> BS・CS (衛星放送) では、同一ネットワークに属するすべてのチャンネルの情報が、放送波の MPEG-2 TS 内の NIT (Network Information Table) や SDT (Service Description Table) というメタデータに含まれています。  
> そのため、 BS・CS1・CS2 の各ネットワークごとに1つの物理チャンネルをスキャンするだけで、そのネットワークに属するすべてのチャンネルを一括で検出することができます。

> [!NOTE]  
> 地上波の物理チャンネルのうち 53ch - 62ch はすでに廃止されていますが、依然として一部ケーブルテレビのコミュニティチャンネル (自主放送) にて利用されているため、スキャン対象に含めています。

> [!IMPORTANT]  
> 検証環境がないため、ISDB-T の C13 - C63ch (周波数変換パススルー方式) と、ISDB-C (トランスモジュレーション方式) で放送されているチャンネルのスキャンには対応していません。 

- [ISDBScanner](#isdbscanner)
  - [対応チューナー](#対応チューナー)
  - [対応出力フォーマット](#対応出力フォーマット)
  - [インストール](#インストール)
  - [使い方](#使い方)
  - [注意事項](#注意事項)
  - [License](#license)

## 対応チューナー

現時点では、いわゆる chardev 版ドライバを使用するチューナーのみに対応しています。  
recisdb が V4L2 DVB インターフェイスに対応していないため、現時点では V4L2 DVB 版ドライバを使用するチューナーには対応していません。  

[px4_drv](https://github.com/tsukumijima/px4_drv) 対応チューナー以外での動作は検証していませんが、おそらく動作すると思います。

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

## 対応出力フォーマット

ISDBScanner は、引数で指定されたディレクトリに複数のファイルを出力します。  
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

## インストール

執筆中…

## 使い方

執筆中…


## 注意事項

- **深夜にチャンネルスキャンを行うと、停波中のチャンネルがスキャン結果から漏れてしまいます。**
  - 特に NHK Eテレは毎日深夜に放送を休止しているため、深夜にスキャンを行うとスキャン結果から漏れてしまいます。
  - できるだけ (停波中のチャンネルがない) 日中時間帯のチャンネルスキャンをおすすめします。
- **EDCB-Wine のチャンネル設定ファイルを実稼働環境に反映する場合は、EDCB-Wine で利用している Mirakurun / mirakc のチャンネル設定ファイルも、必ず同時に更新してください。**
  - BonDriver は物理チャンネル自体の数値ではなく基本 0 からの連番となる「通し番号」でチャンネル切り替えを行う仕様になっていて、ChSet4.txt にはこの通し番号が記載されています。
    - EDCB-Wine で利用している BonDriver_mirakc の場合、Mirakurun / mirakc 側で登録した物理チャンネルの配列インデックスがそのまま「通し番号」になります。
  - つまり、**Mirakurun / mirakc のチャンネル設定ファイルを変更して登録中の物理チャンネルを増減させると、この BonDriver の「通し番号」がズレてしまい、再度 ChSet4.txt を生成し直さない限り正しくチャンネル切り替えが行えない状態に陥ります。**
    - 実際私はこれが原因で録画に失敗したことがあります…。
    - こうした事態を避けるため、**EDCB-Wine と Mirakurun / mirakc のチャンネル設定ファイルは、片方だけを更新するのではなく、常に両方を同時に更新するようにしてください。**

## License

[MIT License](License.txt)
