# All Around You Preview：Agent 安裝與驗收手冊

本手冊適用於學員收到的 **All-Around-You-Preview** 可攜資料夾，主程式為 `AllAroundYouPreview.exe`。目標是 Windows x64；其他架構與每位學員的音訊硬體尚未完成驗收。請以學員電腦當次結果回報，勿把作者電腦的測試當成通用相容保證。

應用程式、執行環境與官方標準 VB-CABLE Pack46 已包含在套件中。不需要 Python、Node.js、Electron、Git、Visual Studio、套件管理器或編譯步驟。主程式為可攜版；VB-CABLE 是另外安裝到 Windows 的音訊驅動。

## 1. 操作原則與完成條件

學員已要求協助安裝時，可完成必要的本機檢查、備份、設定與驗證。已取得的操作授權持續有效，無須每條命令重新確認。以下需要實際資訊或人的操作：

- **位置對應**：裝置名稱無法證明實體位置。請向學員確認 FL 左前、FR 右前、RL 左後、RR 右後各用哪個 Windows 裝置。
- **聲音與麥克風**：第一次發聲或校正前通知會播放短測試音，確認房間已準備、音量適中、麥克風放在座位。若學員已明確表示可以開始，依這次授權完成同一輪測試。
- **UAC／重新啟動**：需要學員在自己的桌面處理 UAC；需要重開機時停在可恢復的狀態，說明原因，讓學員決定時間。不要自動重開機。
- **安全阻擋**：不要停用 Defender／SmartScreen、修改執行政策來繞過組織控管、關閉驅動簽章驗證或修改官方驅動。

完成驗收包含四類證據：套件自檢、實際路由、四位置實聽、延遲量測。最後清楚區分已完成與未完成的項目。`--check` 只測程式數值運算與端點探索，沒有實際喇叭播放或房間錄音；成功不等同路由可用，也不等同使用者已聽見。

## 2. 解壓、位置與備份

1. 完整解壓到持久的使用者可寫位置，例如 `%LOCALAPPDATA%\Programs\All-Around-You-Preview`。若學員已指定資料夾，使用其指定位置。
2. 不在 ZIP 檢視器、暫存資料夾或很快會刪除的下載解壓暫存目錄執行。保留 EXE 同層的 `_internal` 及所有子檔案。
3. 執行前讀套件的 `build-manifest.json` 與 `SHA256SUMS.txt`，核對版本／架構與完整性。ZIP 外另附 `.sha256` 時也要比較 ZIP 本身。雜湊可偵測解壓遺漏或檔案變動；同包附上的雜湊清單無法單獨證明發行者身分。
4. 舊版與新品牌共用 `%LOCALAPPDATA%\DoubleSoundSurround`。先備份既有 `settings.json`、`status.json` 與 `endpoint-backups`。`status.json` 僅供診斷，復原設定時不把舊狀態檔當成目前狀態。
5. 套件不應包含作者的 `settings.json`、`status.json`、裝置 ID、量測報告、帳號憑證或錄音。若看到這類個人檔案，先停止套用並請提供者檢查套件。

下例以 **Windows PowerShell 5.1 或 PowerShell 7** 執行。將 `$AayRoot` 改為實際完整解壓位置；不要保留範例位置而在另一個資料夾執行。

```powershell
$ErrorActionPreference = 'Stop'
$AayOs = Get-CimInstance -ClassName Win32_OperatingSystem
$AayOs | Select-Object Caption, Version, OSArchitecture
# 另核對處理器架構；ARM64 即使可模擬部分 x64 程式，仍不在本版驗收目標內。
$AayCpu = Get-CimInstance -ClassName Win32_Processor | Select-Object -First 1
if ($AayCpu.Architecture -ne 9) { throw '本包目標為 x64 Windows；這台處理器架構不在已測目標內。' }
$AayRoot = Join-Path $env:LOCALAPPDATA 'Programs\All-Around-You-Preview'
$AayRoot = (Resolve-Path -LiteralPath $AayRoot).Path
$AayExe = Join-Path $AayRoot 'AllAroundYouPreview.exe'
$AayData = Join-Path $env:LOCALAPPDATA 'DoubleSoundSurround'
$AaySession = Join-Path $env:LOCALAPPDATA ('AllAroundYouPreview-Agent\sessions\' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N'))
if (-not (Test-Path -LiteralPath $AayExe -PathType Leaf)) { throw '找不到主程式；請確認完整解壓位置。' }
if (-not (Test-Path -LiteralPath (Join-Path $AayRoot '_internal') -PathType Container)) { throw '缺少 _internal，請完整重新解壓。' }
New-Item -ItemType Directory -Path $AaySession -Force | Out-Null
if (Test-Path -LiteralPath (Join-Path $AayData 'settings.json')) {
    Copy-Item -LiteralPath (Join-Path $AayData 'settings.json') -Destination (Join-Path $AaySession 'settings.before.json')
}
if (Test-Path -LiteralPath (Join-Path $AayData 'status.json')) {
    Copy-Item -LiteralPath (Join-Path $AayData 'status.json') -Destination (Join-Path $AaySession 'status.before.json')
}
if (Test-Path -LiteralPath (Join-Path $AayData 'endpoint-backups') -PathType Container) {
    Copy-Item -LiteralPath (Join-Path $AayData 'endpoint-backups') -Destination (Join-Path $AaySession 'endpoint-backups.before') -Recurse
}
```

如需還原舊版，保留其完整程式資料夾。新舊版本不要同時路由；它們共用設定與單一常駐實例識別。

建置資訊含 `product`、`version`、`platform`、`built_at_utc`、`upstream`、`entrypoint`、`driver`、`validation` 與 `files`。`validation.physical_acoustic_calibration` 與 `validation.clean_second_pc_test` 是發行時的驗收界線；本版的新電腦驗收仍待各學員現場完成。不要將它們自行改為通過。

驗證隨包雜湊清單（包含 `build-manifest.json`，不包含清單自身）：

```powershell
$AayManifestPath = Join-Path $AayRoot 'build-manifest.json'
$AayManifest = Get-Content -LiteralPath $AayManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($AayManifest.product -ne 'All Around You Preview' -or $AayManifest.entrypoint -ne 'AllAroundYouPreview.exe') { throw '套件識別不符。' }
$AayRootPrefix = $AayRoot.TrimEnd('\') + '\'
$AayHashLines = Get-Content -LiteralPath (Join-Path $AayRoot 'SHA256SUMS.txt') -Encoding UTF8
if (-not $AayHashLines) { throw '雜湊清單為空。' }
foreach ($AayLine in $AayHashLines) {
    if ($AayLine -notmatch '^([a-fA-F0-9]{64})\s+[*]?(.+)$') { throw '雜湊清單格式無法辨識。' }
    $AayExpectedHash = $Matches[1]
    $AayRelativePath = $Matches[2]
    $AayFile = [IO.Path]::GetFullPath((Join-Path $AayRoot $AayRelativePath))
    if (-not $AayFile.StartsWith($AayRootPrefix, [StringComparison]::OrdinalIgnoreCase)) { throw '雜湊清單路徑超出套件資料夾。' }
    if (-not (Test-Path -LiteralPath $AayFile -PathType Leaf)) { throw "缺少檔案：$AayRelativePath" }
    if ((Get-FileHash -LiteralPath $AayFile -Algorithm SHA256).Hash -ne $AayExpectedHash) { throw "雜湊不符：$AayRelativePath" }
}
$AayManifest | ConvertTo-Json -Depth 6
```

上例最後輸出可能包含完整檔案清單；agent 可只向學員摘要版本、架構與驗證結果。以新解壓套件核對，避免把學員後來另存到資料夾的個人報告混進發行檔案。

## 3. 以 JSON 報告執行命令

此 EXE 為視窗程式。不要只靠終端輸出、`$LASTEXITCODE` 或檔案曾經存在判定成功。有限時命令一律以 `Start-Process -Wait -PassThru -WindowStyle Hidden` 啟動，取得該程序的 `ExitCode`，再解析當次新報告的 `ok`。下列函式會處理路徑中的空格，並為每次呼叫使用不同報告名稱。

```powershell
function ConvertTo-AayArgument {
    param([AllowEmptyString()][string]$Value)
    # Windows 命令列規則：雙引號前及結尾的反斜線需要成對跳脫。
    $Quoted = [regex]::Replace($Value, '(\\*)"', '$1$1\"')
    $Quoted = [regex]::Replace($Quoted, '(\\+)$', '$1$1')
    return '"' + $Quoted + '"'
}

function Invoke-Aay {
    param([Parameter(Mandatory = $true)][string[]]$AayArgs)
    $ReportPath = Join-Path $AaySession ((Get-Date -Format 'HHmmss-fff') + '-' + [guid]::NewGuid().ToString('N') + '.json')
    $AllArgs = @('--agent') + $AayArgs + @('--report', $ReportPath)
    $ArgumentLine = ($AllArgs | ForEach-Object { ConvertTo-AayArgument $_ }) -join ' '
    $Process = Start-Process -FilePath $AayExe -ArgumentList $ArgumentLine -Wait -PassThru -WindowStyle Hidden
    if (-not (Test-Path -LiteralPath $ReportPath -PathType Leaf)) {
        throw "命令未產生報告；ExitCode=$($Process.ExitCode)，請檢查系統阻擋或啟動錯誤。"
    }
    $Report = Get-Content -LiteralPath $ReportPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($Process.ExitCode -ne 0 -or $Report.ok -ne $true) {
        throw "命令失敗；ExitCode=$($Process.ExitCode)；報告=$ReportPath；內容=$($Report | ConvertTo-Json -Depth 12 -Compress)"
    }
    [pscustomobject]@{ ExitCode = $Process.ExitCode; ReportPath = $ReportPath; Report = $Report }
}
```

每份 `--agent` 報告至少有 `ok`、`action` 與 `timestamp_utc`。失敗回傳非零結束碼與錯誤報告。讀取錯誤後修正原因，再以新報告重試，不把前次成功報告混用。報告必須存於獨立的持久資料夾；CLI 會拒絕將報告寫入 `%LOCALAPPDATA%\DoubleSoundSurround` 或其子目錄，避免覆蓋應用程式資料。已存在的報告檔，以及與 `--input` 相同的路徑也會被拒絕。報告路徑被拒絕或不可寫時可能無新報告，請以退出碼及路徑檢查判讀。報告可能含本機端點 ID、裝置名稱及路徑；留在學員電腦，分享前由學員確認內容。

| 命令 | 成功報告主要欄位 |
| --- | --- |
| `devices` | `inventory`、`endpoint`、`settings_path`、`default_render_ids` |
| `install-driver` | `driver`，包含 `reboot_required` |
| `configure-endpoint` | `endpoint`，包含格式／名稱及 `backup_path` |
| `profile` | `settings_path`、`backup_path`、`profile`、`input_profile`、`mapping`；首次無既有設定時備份為 null |
| `test` | `role`、`completed`、`audible_confirmation_required` |
| `calibrate`／`verify` | `calibration`、`applied`、`microphone_audio_saved`；`calibrate --apply` 另含 `settings_path`、`backup_path`、`profile`、`input_profile` |
| `startup` | `enabled`、`command` |
| `defaults` | 原始／套用後各角色端點、操作狀態及還原快照；完整保留報告供 `--restore` 使用 |

### 自檢

`--check` 是獨立命令，不經過 `--agent`：

```powershell
$AayCheckPath = Join-Path $AaySession ('self-check-' + [guid]::NewGuid().ToString('N') + '.json')
$AayCheckArgs = (@('--check', $AayCheckPath) | ForEach-Object { ConvertTo-AayArgument $_ }) -join ' '
$AayCheckProcess = Start-Process -FilePath $AayExe -ArgumentList $AayCheckArgs -Wait -PassThru -WindowStyle Hidden
if (-not (Test-Path -LiteralPath $AayCheckPath)) { throw '自檢沒有產生報告。' }
$AayCheck = Get-Content -LiteralPath $AayCheckPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($AayCheckProcess.ExitCode -ne 0 -or $AayCheck.ok -ne $true) { throw "自檢失敗：$AayCheckPath" }
```

自檢通過後才能繼續。虛擬端點尚未安裝時，部分端點資訊可能為空；記錄此狀態，接著完成端點安裝。自檢不會替你選喇叭、安裝驅動、校正或啟動路由。

### 停止現有常駐

修改設定、端點、啟動項目，或執行位置測試／校正前，先退出常駐，等舊 PID 真正離開。只按視窗右上角 X 會留在通知區。

```powershell
$AayOldPid = $null
$AayStatusPath = Join-Path $AayData 'status.json'
if (Test-Path -LiteralPath $AayStatusPath) {
    $AayOldStatus = Get-Content -LiteralPath $AayStatusPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $AayOldPid = $AayOldStatus.pid
}
$AayQuit = Start-Process -FilePath $AayExe -ArgumentList '--quit' -Wait -PassThru -WindowStyle Hidden
if ($AayQuit.ExitCode -ne 0) { throw '退出命令失敗。' }
if ($AayOldPid) {
    $AayOldProcess = Get-Process -Id $AayOldPid -ErrorAction SilentlyContinue
    if ($AayOldProcess -and $AayOldProcess.ProcessName -in @('AllAroundYouPreview', 'EasySurround')) {
        Wait-Process -Id $AayOldPid -Timeout 15 -ErrorAction Stop
    }
}
```

若常駐仍未退出，停止依賴它的後續命令並查看狀態。不要任意終止其他程式，或直接覆寫執行中的 `settings.json`。若 Windows 此時仍選 CABLE Input，先恢復實體輸出，避免學員誤以為系統音訊故障。

## 4. 列出本機裝置，確認位置

```powershell
$AayDevices = Invoke-Aay -AayArgs @('devices')
$AayDevices.Report | ConvertTo-Json -Depth 12
```

`devices` 報告提供 `inventory`、`endpoint`、`settings_path`、`default_render_ids`。使用本次 `inventory` 中的完整裝置 ID；`outputs` 是可用輸出，`mics` 是實體麥克風，`inputs` 是來源清單。從 `inventory.inputs` 找標準 CABLE Input 的 WASAPI loopback 來源，並以 `endpoint` 資料核對。請原樣保留完整 ID，勿裁掉 GUID 或把顯示名稱當 ID。

向學員列出可選裝置與通道數，一次確認四個位置與麥克風。可使用下表，不要憑「JBL」、「Realtek」等名稱猜位置：

| 位置 | 要由學員確認的實體位置 | 設定欄位 |
| --- | --- | --- |
| FL | 座位前方左邊 | `channels.FL` |
| FR | 座位前方右邊 | `channels.FR` |
| RL | 座位後方左邊 | `channels.RL` |
| RR | 座位後方右邊 | `channels.RR` |

支援四個獨立端點，也支援前方一組立體聲加後方兩顆獨立喇叭，或前後各一組立體聲。共享同一立體聲端點的兩個位置依 FL、FR、RL、RR 順序分配到該端點的左、右聲道。因此典型前方成對設定是 FL 與 FR 使用相同 ID；後方成對是 RL 與 RR 使用相同 ID。

一個端點最多分配兩個位置；原生單聲道端點只能分配一個位置。單一位置使用立體聲端點時，該位置內容會同時送到該裝置的左右聲道。來源虛擬端點不得同時當作任何位置的輸出，以免回授。Windows 若只顯示一個合併後的藍牙端點，程式無法額外拆出兩個獨立裝置。

## 5. 虛擬音訊端點

先依 `devices.endpoint` 判斷是否已有標準 VB-CABLE。已有可用端點就跳過安裝，避免覆蓋原有驅動。

```powershell
# 僅在缺少標準 VB-CABLE 時執行；會要求官方驅動安裝的 UAC。
$AayDriver = Invoke-Aay -AayArgs @('install-driver')
$AayDriver.Report | ConvertTo-Json -Depth 12
```

安裝使用包內原樣官方 Pack46，可能需要管理員授權。UAC 取消不代表安裝完成。若報告需要重新啟動，保存當次結果，請學員重啟後再從 `devices` 繼續；不要自動重啟。CLI 完成後仍需重新列出裝置，不能假設 Windows 已經建立可用端點。

```powershell
$AayEndpoint = Invoke-Aay -AayArgs @('configure-endpoint')
$AayEndpoint.Report | ConvertTo-Json -Depth 12
$AayDevices = Invoke-Aay -AayArgs @('devices')
```

確認標準播放端點為 **CABLE Input (VB-Audio Virtual Cable)**、4 聲道、48,000 Hz、聲道遮罩 `0x33`（十進位 51，FL／FR／RL／RR）。此功能保持廠商裝置名稱。請勿使用 CABLE In 16ch 或錄音端 CABLE Output 代替標準 Speaker 端點。

`configure-endpoint` 只設定入口格式；它不代表常駐已啟動、實體喇叭已選好、Windows 預設輸出已切換。原端點格式備份位於 `%LOCALAPPDATA%\DoubleSoundSurround\endpoint-backups`。

VB-CABLE 控制面板的 **Windows Volume Control** 保持官方預設關閉；本程式會同步來源的 Windows 音量與靜音。開啟兩邊的音量控制可能產生重複衰減，程式會拒絕這種配置。

## 6. 建立學員專屬設定

複製 `profile.example.json` 到 `$AaySession`，例如 `profile.json`，再替換全部佔位字。範例刻意無法直接套用。不要帶入作者或其他電腦的裝置 ID、藍牙補償；每台電腦必須自行確認。

必填欄位：`source_id`、`channels` 的 FL／FR／RL／RR 四個位置，每個位置含 `device_id`、`delay_ms`。延遲範圍 0–500 ms，可為小數。新裝置組合先設 0，後續量測或手動調整。

選填欄位：`mic_id`、`playback_mode`、`rear_volume_percent`、`resident_enabled`，以及對應的顯示名稱。顯示名稱會以當次裝置清單為準，ID 才是識別依據。未知欄位會被拒絕；不要加入註解或自創設定鍵。麥克風欄位填真實 `inventory.mics` ID；無麥克風時移除 `mic_id`，不要保留佔位字。

| 欄位 | 建議／限制 |
| --- | --- |
| `source_id` | 標準 CABLE Input 對應的 `wasapi:loopback:...` 完整 ID |
| `playback_mode` | `all_stereo` 全喇叭立體聲、`simulated` 模擬環繞、`discrete` 原音分流 |
| `rear_volume_percent` | 0–100；全新設定可從 50 開始 |
| `resident_enabled` | 設為 `true` 才會在背景啟動時載入已保存路由 |

新安裝可選 `all_stereo`，便於用一般立體聲節目確認前後都有聲音。已存在的學員設定應保留原模式、音量與有效的同組裝置校正；不要為了示範而自動覆蓋。省略選填欄位時會保留既有值，首次安裝則以程式預設為準。四位置設定每次要完整提供。

```powershell
$AayProfilePath = Join-Path $AaySession 'profile.json'
# 先由 agent 建立並確認 profile.json；下面只負責驗證和套用。
$AayProfile = Get-Content -LiteralPath $AayProfilePath -Raw -Encoding UTF8 | ConvertFrom-Json
$AaySaved = Invoke-Aay -AayArgs @('profile', '--input', $AayProfilePath)
$AaySaved.Report | ConvertTo-Json -Depth 12
if (-not $AaySaved.Report.input_profile) { throw '缺少保存後的 input_profile。' }
$AayProfile = $AaySaved.Report.input_profile
$AayProfile | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $AayProfilePath -Encoding UTF8
```

`profile` 會驗證當前可用 ID、回授風險、每個端點的角色數、延遲與模式，再備份及合併保存。它不會自動更改 Windows 預設輸出或登入啟動。資料存於 `%LOCALAPPDATA%\DoubleSoundSurround\settings.json`，舊名稱維持既有版本相容。

## 7. 位置測試、麥克風校正與驗證

先確保常駐已退出，停止其他播放器，將實體喇叭調到舒適小音量。通知學員接下來有短測試音。請依序測每個位置並由學員確認聲音位置：

```powershell
$AayTestFL = Invoke-Aay -AayArgs @('test', '--input', $AayProfilePath, '--role', 'FL')
$AayTestFR = Invoke-Aay -AayArgs @('test', '--input', $AayProfilePath, '--role', 'FR')
$AayTestRL = Invoke-Aay -AayArgs @('test', '--input', $AayProfilePath, '--role', 'RL')
$AayTestRR = Invoke-Aay -AayArgs @('test', '--input', $AayProfilePath, '--role', 'RR')
```

可依學員回應逐個執行，不必連續一次播完。命令成功只代表對應串流完成；實際哪個位置發聲需要學員確認。若對應錯誤，先修 profile，再重測受影響位置。

測試、測量與驗證會略過播放效果及後方音量，採用測試訊號；**後方音量 0% 無法用來靜音測試音**。測量略過既有延遲，驗證使用現有四個延遲。

### 有麥克風

優先使用獨立 USB／電腦麥克風，放在主要座位耳朵高度，避免移動與背景聲。Bluetooth 喇叭內建麥克風可能讓 Windows 切入通話模式，改變播放品質與延遲；應確認實際端點型態。麥克風只在本機記憶體中分析，不上傳、不儲存錄音。

第一次可先量測並讀報告，約 25 秒：

```powershell
$AayMeasure = Invoke-Aay -AayArgs @('calibrate', '--input', $AayProfilePath)
$AayMeasure.Report | ConvertTo-Json -Depth 12
```

若要量測並一次套用四位置補償，使用：

```powershell
$AayCalibrate = Invoke-Aay -AayArgs @('calibrate', '--input', $AayProfilePath, '--apply')
$AayCalibrate.Report | ConvertTo-Json -Depth 12
```

兩條命令都會實際量測，第二條會再播放一輪；一般安裝可直接使用 `--apply`，不必重複量測。任何位置辨識失敗、回音歧義、時間不穩、有效回合不足或補償超出 500 ms，整輪拒絕套用。不要從失敗報告擷取部分值手動拼成「校正完成」。

四位置補償是把較早到達的聲音延後至最慢位置；無法提前藍牙本身的聲音。`profile` 與 `calibrate --apply` 成功報告提供可直接再輸入的 **`input_profile`**，以及含舊版相容欄位的完整 `profile`。後者不要直接拿來當 `--input`。套用後，把 `input_profile` 保存為下一步輸入，確保驗證測到新延遲。

```powershell
if (-not $AayCalibrate.Report.input_profile) { throw '缺少套用後的 input_profile，先檢查校正報告。' }
$AayProfile = $AayCalibrate.Report.input_profile
$AayProfile | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $AayProfilePath -Encoding UTF8
$AayVerify = Invoke-Aay -AayArgs @('verify', '--input', $AayProfilePath)
$AayVerify.Report | ConvertTo-Json -Depth 12
```

記錄四位置補償、量測穩定度與驗證最大到達差，讓學員知道此結果只反映當次座位／連線。不要僅憑命令成功就宣稱「完全同步」；驗證仍有殘差時如實列出。

### 沒有麥克風

可先完成播放與位置驗收，四位置延遲保留 0 或由學員手動調整。把較快到達的位置加上延遲，範圍 0–500 ms。將結果明確標為「手動調整，未做麥克風校正／驗證」，不要猜補償值，也不要套用其他電腦的值。

### 校正的範圍

藍牙重連、睡眠喚醒、喇叭移動、座位改變後應重新驗證。程式保留每組四位置裝置的補償，但不保證重連後內部延遲完全相同。不同硬體時鐘仍可能逐漸漂移；本預覽版的長時間 ASRC／時鐘同步尚未驗收。補償也會增加整體音訊延遲，影片嘴形需另在播放器調整，即時遊戲操作延遲仍須實測。

## 8. 常駐、登入啟動與 Windows 輸出

確認已保存的 `resident_enabled` 為 `true`。若學員要求登入自動啟動，在常駐尚未啟動時執行：

```powershell
$AayStartup = Invoke-Aay -AayArgs @('startup', '--enable')
```

登入啟動和自動載入路由是兩項設定：`startup --enable` 設定目前使用者登入啟動；`resident_enabled` 決定開啟後是否載入路由。也可在 UI 勾選「開啟程式時自動載入環繞，裝置重連後恢復」及「登入 Windows 時啟動並留在通知區」。

常駐程序會持續執行，因此此處刻意不使用 `-Wait`；使用狀態檔驗收啟動結果：

```powershell
$AayStartedAt = [datetime]::UtcNow
$AayResident = Start-Process -FilePath $AayExe -ArgumentList '--background' -PassThru -WindowStyle Hidden
```

給程式數秒開啟音訊串流，讀取 `%LOCALAPPDATA%\DoubleSoundSurround\status.json`，必要時短間隔重試。不得只確認 EXE 存活。驗收需要同時符合：

- `timestamp_utc` 在本次啟動之後，持續更新且距現在不超過約 10 秒。
- `pid` 是仍存活的本程式程序，核對其路徑確為本次部署的 EXE；不要相信殘留狀態檔或剛好重複使用的 PID。
- `state` 為 `running`、`running` 為 `true`，並確認 `engine_state` 為 `running`。
- `source_id`、四個 `channels` 的精確 ID／延遲、`playback_mode` 與預期一致。

```powershell
$AayStatus = Get-Content -LiteralPath $AayStatusPath -Raw -Encoding UTF8 | ConvertFrom-Json
$AayLiveProcess = Get-Process -Id $AayStatus.pid -ErrorAction Stop
$AayStatusTime = [datetime]::Parse($AayStatus.timestamp_utc).ToUniversalTime()
if ($AayStatusTime -lt $AayStartedAt -or ([datetime]::UtcNow - $AayStatusTime).TotalSeconds -gt 10) { throw '狀態時間過舊。' }
if ($AayLiveProcess.Path -ne $AayExe) { throw '狀態 PID 不是本次部署的程式。' }
if ($AayStatus.state -ne 'running' -or $AayStatus.running -ne $true -or $AayStatus.engine_state -ne 'running') { throw '路由尚未運作。' }
if ($AayStatus.source_id -ne $AayProfile.source_id) { throw '來源不符。' }
foreach ($AayRole in @('FL', 'FR', 'RL', 'RR')) {
    if ($AayStatus.channels.$AayRole.device_id -ne $AayProfile.channels.$AayRole.device_id) { throw "位置 $AayRole 的裝置不符。" }
    if ([double]$AayStatus.channels.$AayRole.delay_ms -ne [double]$AayProfile.channels.$AayRole.delay_ms) { throw "位置 $AayRole 的延遲不符。" }
}
if ($AayProfile.playback_mode -and $AayStatus.playback_mode -ne $AayProfile.playback_mode) { throw '播放模式不符。' }
```

**路由確認運作後，才切換 Windows 預設輸出。** 先保留原本各角色的預設輸出快照。若切換只針對指定播放器，可在該播放器選 CABLE Input，不必改全部 Windows 音效。

```powershell
$AayDefaultSet = Invoke-Aay -AayArgs @('defaults', '--set-source', '--input', $AayProfilePath)
# 這份報告本身是還原快照；保留在持久位置，勿覆寫。
$AayDefaultSnapshot = $AayDefaultSet.ReportPath
```

`defaults --set-source` 允許常駐執行，並再次檢查新鮮狀態、存活 PID、來源與四位置 ID／延遲是否符合保存設定及輸入。若被拒絕，先修正原因；不要繞過檢查直接替學員切換。

確認 Windows 的一般／多媒體／通訊預設角色讀回符合預期。播放一段學員熟悉的節目，詢問前後聲音、音量與延遲。程式 `running` 不能代替實聽。

不要在同次安裝重複執行 `--set-source` 來覆寫第一份原始快照。以第一份有效快照作復原依據。視窗 X 會縮到通知區；雙擊圖示或再次開啟 EXE 可顯示設定。手動按「停止」會暫停當次自動恢復；按「開始」繼續。

## 9. 日常操作與內容限制

| 模式 | 行為 | 驗收方式 |
| --- | --- | --- |
| 全喇叭立體聲 `all_stereo` | 左音送前左／後左，右音送前右／後右 | 用立體聲節目確認前後均有聲音 |
| 模擬環繞 `simulated` | 後方加入差分環境效果，中央人聲可能較弱 | 用有左右差異的節目比較；後方短暫安靜屬可能結果 |
| 原音分流 `discrete` | 按片源聲道分送；兩聲道片源只在前方播放 | 用四聲道測試檔或多聲道 PCM 片源 |

變更模式時停止路由、選擇模式、再啟動。後方音量可在播放中調整，0–100% 同時控制 RL／RR。聲道配置保留「自動」。即使節目為立體聲，四聲道虛擬入口也可承載前兩個聲道。

全喇叭立體聲及模擬環繞會先把多聲道內容混成立體聲再加效果。若要保留原生後方方位，用原音分流。模擬環繞的 12 ms 環境效果與四位置藍牙補償分開，不會改寫校正值。

電影或遊戲需輸出 PCM；Dolby／DTS 位元流直通不在此路由範圍。不同播放器的 5.1／7.1 到四聲道混音仍須實際檢查。驗證四聲道順序時使用隨附的 `4.0-前左前右後左後右.wav`，模式設原音分流，播放器輸出到 CABLE Input；學員確認 FL、FR、RL、RR 依序發聲後，再恢復其原本播放模式。

## 10. 常見問題與處理

| 現象／報告 | 檢查與處理 | 不可誤報 |
| --- | --- | --- |
| 缺少 `_internal`、DLL 或主程式無法載入 | 比對雜湊，完整重新解壓到持久路徑，保留完整目錄 | 不宣稱已安裝成功 |
| 未簽章／SmartScreen／組織防護阻擋 | 保留原始訊息與來源，確認發行檔完整；請使用者或管理員處理允許政策 | 不指示停用保護或修改驅動簽章 |
| UAC 取消或驅動安裝失敗 | 保留安裝報告；確認學員是否可取得管理員協助 | 不把啟動安裝器當完成安裝 |
| 要求重開機／端點尚未出現 | 保存進度，讓學員安排重啟，重啟後重新列裝置 | 不自動重啟、不先切到無效來源 |
| 裝置離線、改名或重連後無法恢復 | 重新列出 exact ID；等待原裝置，ID 已變時向學員確認新映射 | 不靜默改用另一顆喇叭 |
| 來源與輸出相同／有回授風險 | 來源只能為擷取入口，各位置選實體輸出 | 不繞過驗證強行啟動 |
| Windows 選 CABLE Input 後無聲 | 查 fresh status、PID、running、四位置、Windows／實體音量及靜音；路由停了就先恢復實體輸出 | 不只看舊 `status.json` |
| 原音分流後方無聲 | 先確認片源是否有後方聲道，再用四聲道測試；一般立體聲可用全喇叭立體聲 | 不把立體聲無後方當硬體故障 |
| 模擬環繞中央人聲後方弱 | 此效果會降低左右相同內容；用有空間感的節目比較 | 不承諾每段都有後方聲音 |
| 音量極小、重複衰減 | 查 Windows 音量／靜音、後方音量、實體音量，以及 VB-CABLE Windows Volume Control 是否仍關閉 | 不靠提高測試音掩蓋配置錯誤 |
| Bluetooth 通話／Hands-Free 低音質 | 檢查目前連線型態，選合適的播放端點及獨立麥克風，重新量測 | 不以舊延遲假設新模式相同 |
| 麥克風不可用／權限拒絕 | Windows「隱私權與安全性 → 麥克風」確認允許桌面應用程式，重查裝置 ID | 不用 loopback 假裝實體麥克風 |
| 四位置中部分校正失敗 | 整次不套值；調整音量、座位、房間噪音／回音，重測全四位置 | 不把部分結果拼成成功 |
| JSON 失敗或結束碼非零 | 讀當次 report 的 error；檢查佔位字、欄位、路徑、權限與常駐是否仍在 | 不忽略錯誤繼續切預設輸出 |
| 長時間不同步或重連後偏移 | 重新驗證／校正並記錄時間；長期時鐘漂移列為未完成驗收 | 不把一次校正當永久鎖定同步 |

## 11. 停止、復原、更新與移除

停止使用前，先恢復 Windows 音訊輸出，再退出常駐：

```powershell
$AayRestored = Invoke-Aay -AayArgs @('defaults', '--restore', '--input', $AayDefaultSnapshot)
$AayRestored.Report | ConvertTo-Json -Depth 12
$AayQuit = Start-Process -FilePath $AayExe -ArgumentList '--quit' -Wait -PassThru -WindowStyle Hidden
```

還原只應變更目前仍指向本程式所設虛擬端點的角色；若學員已自行改成其他喇叭，保留學員後來的選擇。若沒有有效快照，請學員在 Windows「設定 → 系統 → 音效 → 輸出」選回原先實體喇叭，勿猜預設裝置。直接退出 UI 不會自動執行 agent 的還原命令。

取消登入啟動：先退出常駐，再執行下列命令，或在 UI 取消登入啟動勾選：

```powershell
$AayStartupOff = Invoke-Aay -AayArgs @('startup', '--disable')
```

應用程式的啟動項目在目前使用者的 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`，值名稱仍為 `DoubleSoundSurround`，以相容舊版。只修改本程式的值，不動其他登入項目。

更新可攜版時保留舊完整資料夾及設定備份，退出常駐後再部署新版。搬動資料夾後，需要在新位置重新啟用登入啟動，確保路徑指向新 EXE。使用已保存四位置設定時先重查 ID 與狀態，毋須把學員設定寫進要分享的 ZIP。

恢復 `settings.json` 時先退出常駐，把目前設定另存備份，再用自己的 `settings.before.json` 復原；不可用作者或另一名學員的設定。端點原格式備份在 `endpoint-backups`，需要恢復時根據備份在 Windows 音效設定中核對；不要盲目修改登錄值。

移除程式前先切回實體輸出、退出常駐、取消登入啟動。保留設定備份後可移除程式資料夾。VB-CABLE 是獨立驅動，可能被其他軟體使用；只有使用者確定要移除它時，才使用官方安裝器的 Remove Driver 並依官方指示處理重啟，不手動刪除驅動檔。

## 12. 來源、授權與資料範圍

All Around You Preview 是基於 EasySurround 的 Windows 預覽改作。包內保留原專案 MIT 授權及相關第三方授權；改品牌不移除原作者歸屬。

VB-CABLE 由 **VB-Audio Software** 開發，採 **donationware** 發行。官方入口：[vb-cable.com](https://vb-cable.com/)；授權條款：[VB-Audio Licensing](https://vb-audio.com/Services/licensing.htm)。本包隨附官方標準 Pack46 原始 ZIP，未修改驅動、簽章或安裝器。歡迎學員依官方頁面捐款支持或購買適用授權；企業／專業部署應按官方條款確認其授權需求。

音訊路由與麥克風分析在本機執行。麥克風錄音不寫檔、不上傳。設定與診斷報告含裝置名稱／ID、路徑、PID、時間及量測數值；不要把它們當成可隨意公開的範例。此安裝流程不需要 API 金鑰、雲端帳號或外部服務。

## 13. Agent 最後交付模板

請用繁體中文向學員回報，附本機檔案路徑，並明確留下後續操作：

```text
All Around You Preview 安裝結果

已驗證：
- 套件版本／安裝路徑／檔案完整性：
- --check 結果與報告路徑：
- 虛擬端點名稱、4 聲道／48 kHz／遮罩：
- 四位置裝置對應與各自延遲：
- 播放模式／後方音量：
- 最近 status 時間、PID、running、設定比對：
- Windows 預設輸出／還原快照路徑：
- 登入啟動與自動載入：
- 校正／驗證數值及報告路徑（若執行）：

使用者已確認：
- 實際 FL、FR、RL、RR 發聲位置：
- 實際節目播放、音量與同步感：

未測：
- 未執行的麥克風驗證／登入重啟／藍牙重連／長時間同步：

阻擋：
- 錯誤原文、失敗階段、需要的使用者操作（若無則填無）：

日常開啟／停止方法：
Windows 輸出還原方法與備份位置：
```

未取得使用者實聽確認時，保留為待確認。不要將自檢、程序存活、零音量寫入測試或模擬校正數據當成學員的聲學驗收。
