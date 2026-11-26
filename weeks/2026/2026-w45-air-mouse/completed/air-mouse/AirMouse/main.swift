// AirPods 空中滑鼠（開蓋版）
// 讀取充電盒內（開蓋）AirPods 的動作感測資料，轉成游標移動與點擊。
// 左右轉動盒子 → 游標左右；前端上下抬 → 游標上下；停住後點按盒子 → 左鍵。

import AppKit
import ApplicationServices
import Carbon.HIToolbox
import CoreMotion
import IOBluetooth

// MARK: - 向量運算

struct V3 {
    var x: Double, y: Double, z: Double
    init(_ x: Double, _ y: Double, _ z: Double) { self.x = x; self.y = y; self.z = z }
    init?(_ a: [Double]?) {
        guard let a, a.count == 3 else { return nil }
        self.init(a[0], a[1], a[2])
    }
    static func + (l: V3, r: V3) -> V3 { V3(l.x + r.x, l.y + r.y, l.z + r.z) }
    static func - (l: V3, r: V3) -> V3 { V3(l.x - r.x, l.y - r.y, l.z - r.z) }
    static func * (l: V3, s: Double) -> V3 { V3(l.x * s, l.y * s, l.z * s) }
    func dot(_ o: V3) -> Double { x * o.x + y * o.y + z * o.z }
    func cross(_ o: V3) -> V3 { V3(y * o.z - z * o.y, z * o.x - x * o.z, x * o.y - y * o.x) }
    var length: Double { dot(self).squareRoot() }
    var unit: V3? { let l = length; return l > 1e-6 ? self * (1 / l) : nil }
    var array: [Double] { [x, y, z] }
    static let zero = V3(0, 0, 0)
}

func uptime() -> Double { ProcessInfo.processInfo.systemUptime }

func sourceName(_ source: Int) -> String {
    switch source {
    case 1: return "左耳"
    case 2: return "右耳"
    default: return "耳機"
    }
}

// MARK: - 設定（存在 UserDefaults）

final class Settings {
    private let d = UserDefaults.standard
    static let speedNames = ["慢", "中", "快"]
    static let gains: [Double] = [900, 1500, 2300]   // 每弧度對應的游標點數（未加速前）

    var speedIndex: Int {
        get { min(max(d.object(forKey: "speedIndex") as? Int ?? 1, 0), 2) }
        set { d.set(newValue, forKey: "speedIndex") }
    }
    var gain: Double { Settings.gains[speedIndex] }
    var invertY: Bool {
        get { d.bool(forKey: "invertY") }
        set { d.set(newValue, forKey: "invertY") }
    }
    /// 輕觸盒子＝左鍵；輕觸兩下＝雙擊。
    var tapClicks: Bool {
        get { d.object(forKey: "tapClicks") as? Bool ?? true }
        set { d.set(newValue, forKey: "tapClicks") }
    }
    static let tapPresets: [(name: String, value: Double)] = [("低（只抓用力按）", 0.40), ("中", 0.30), ("高（細微點按）", 0.16)]
    /// 加速度單點尖峰門檻（g）；點按校正測試會寫入個人化的值。
    var tapThreshold: Double {
        get { min(max(d.object(forKey: "tapThreshold") as? Double ?? 0.30, 0.06), 1.0) }
        set { d.set(newValue, forKey: "tapThreshold") }
    }
    var tapThresholdFromTest: Bool {
        get { d.bool(forKey: "tapThresholdFromTest") }
        set { d.set(newValue, forKey: "tapThresholdFromTest") }
    }
    var autoReconnect: Bool {
        get { d.object(forKey: "autoReconnect") as? Bool ?? true }
        set { d.set(newValue, forKey: "autoReconnect") }
    }
    var preferredAddress: String? {
        get { d.string(forKey: "preferredAddress") }
        set { d.set(newValue, forKey: "preferredAddress") }
    }
    /// 盒子「前端」方向在該耳機感測器座標中的單位向量；左右耳各自校正。
    func forward(for source: Int) -> V3? { V3(d.array(forKey: "forward.\(source)") as? [Double]) }
    func setForward(_ f: V3, for source: Int) { d.set(f.array, forKey: "forward.\(source)") }
}

// MARK: - JSONL 紀錄

final class EventLog {
    let directory: URL
    let url: URL
    private let handle: FileHandle?
    private let iso = ISO8601DateFormatter()

    init(directory: URL) {
        self.directory = directory
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let stamp = ISO8601DateFormatter().string(from: Date()).replacingOccurrences(of: ":", with: "-")
        url = directory.appendingPathComponent("airmouse-\(stamp).jsonl")
        FileManager.default.createFile(atPath: url.path, contents: nil)
        handle = try? FileHandle(forWritingTo: url)
    }

    func write(_ type: String, _ fields: [String: Any] = [:]) {
        var object = fields
        let now = Date()
        object["event"] = type
        object["unixTime"] = now.timeIntervalSince1970
        object["wallTime"] = iso.string(from: now)
        guard JSONSerialization.isValidJSONObject(object),
              let data = try? JSONSerialization.data(withJSONObject: object, options: [.sortedKeys]) else { return }
        handle?.write(data)
        handle?.write(Data([0x0A]))
    }
}

// MARK: - 游標驅動：50 Hz 感測資料 → 120 Hz 平滑移動

final class CursorDriver {
    var enabled = false { didSet { if !enabled { halt() } } }
    var gain = 1500.0
    var invertY = false
    private(set) var clicks = 0

    private var vx = 0.0, vy = 0.0          // 目前游標速度（點／秒）
    private var lastInput = 0.0
    private var lastTick = uptime()
    private var residualX = 0.0, residualY = 0.0
    private var displays: [CGRect] = []
    private var marks: [CGPoint] = []       // 最近幾筆感測資料到達時的游標位置
    private let source = CGEventSource(stateID: .hidSystemState)
    private var lastClickTime = 0.0
    private var lastClickPoint = CGPoint.zero
    private var lastClickButton = CGMouseButton.left
    private var clickCount = 0
    private var timer: Timer?

    init() {
        // 預設送出合成事件後會暫停實體觸控板 0.25 秒；設為 0 讓兩者可以並用。
        source?.localEventsSuppressionInterval = 0
        refreshDisplays()
        let t = Timer(timeInterval: 1.0 / 120.0, repeats: true) { [weak self] _ in self?.tick() }
        RunLoop.main.add(t, forMode: .common)
        timer = t
    }

    func refreshDisplays() {
        var count: UInt32 = 0
        CGGetActiveDisplayList(0, nil, &count)
        var ids = [CGDirectDisplayID](repeating: 0, count: Int(max(count, 1)))
        CGGetActiveDisplayList(count, &ids, &count)
        displays = ids.prefix(Int(count)).map { CGDisplayBounds($0) }
    }

    /// yawRate：繞垂直軸角速度；pitchRate：繞水平左右軸角速度（rad/s）。
    func input(yawRate: Double, pitchRate: Double, suppress: Bool, now: Double) {
        lastInput = now
        if let p = currentLocation() {
            marks.append(p)
            if marks.count > 3 { marks.removeFirst() }
        }
        if suppress { halt(); return }
        let rx = -yawRate                       // 向右轉（俯視順時針）→ 游標往右
        let ry = invertY ? pitchRate : -pitchRate // 前端抬起 → 游標往上（螢幕 y 向下為正）
        let w = (rx * rx + ry * ry).squareRoot()
        var tx = 0.0, ty = 0.0
        let deadZone = 0.035                    // 約 2°/s 以下視為手抖
        if w > deadZone {
            let effective = w - deadZone
            let acceleration = min(2.6, 0.35 + 0.65 * effective) // 慢轉精細、快轉跑得遠
            let speed = gain * effective * acceleration
            tx = rx / w * speed
            ty = ry / w * speed
        }
        vx += 0.6 * (tx - vx)
        vy += 0.6 * (ty - vy)
    }

    func halt() { vx = 0; vy = 0 }

    private func tick() {
        let now = uptime()
        let dt = min(max(now - lastTick, 0), 0.05)
        lastTick = now
        guard enabled else { return }
        if now - lastInput > 0.15 { halt(); return }   // 資料一停就不再移動
        let dx = vx * dt, dy = vy * dt
        guard abs(dx) + abs(dy) > 0.01 else { return }
        move(dx: dx, dy: dy)
    }

    private func currentLocation() -> CGPoint? { CGEvent(source: nil)?.location }

    private func clamp(_ p: CGPoint, from current: CGPoint) -> CGPoint {
        if displays.contains(where: { $0.contains(p) }) { return p }
        guard let rect = displays.first(where: { $0.contains(current) }) ?? displays.first else { return p }
        return CGPoint(x: min(max(p.x, rect.minX), rect.maxX - 1),
                       y: min(max(p.y, rect.minY), rect.maxY - 1))
    }

    private func move(dx: Double, dy: Double) {
        guard let current = currentLocation() else { return }
        let target = clamp(CGPoint(x: Double(current.x) + dx, y: Double(current.y) + dy), from: current)
        let dragging = CGEventSource.buttonState(.combinedSessionState, button: .left)
        guard let event = CGEvent(mouseEventSource: source,
                                  mouseType: dragging ? .leftMouseDragged : .mouseMoved,
                                  mouseCursorPosition: target,
                                  mouseButton: .left) else { return }
        residualX += Double(target.x - current.x)
        residualY += Double(target.y - current.y)
        let ix = residualX.rounded(.towardZero), iy = residualY.rounded(.towardZero)
        residualX -= ix
        residualY -= iy
        event.setIntegerValueField(.mouseEventDeltaX, value: Int64(ix))
        event.setIntegerValueField(.mouseEventDeltaY, value: Int64(iy))
        event.post(tap: .cghidEventTap)
    }

    /// 輕觸那一下會讓轉速跳一格、游標跟著晃；把游標拉回輕觸前的位置再點。
    func tapClick() {
        halt()
        guard let p = marks.last ?? currentLocation() else { return }
        if let back = CGEvent(mouseEventSource: source, mouseType: .mouseMoved, mouseCursorPosition: p, mouseButton: .left) {
            back.post(tap: .cghidEventTap)
        }
        click(.left, at: p)
    }

    func click(_ button: CGMouseButton, at point: CGPoint? = nil) {
        guard let p = point ?? currentLocation() else { return }
        let now = uptime()
        let near = hypot(Double(p.x - lastClickPoint.x), Double(p.y - lastClickPoint.y)) < 6
        if button == lastClickButton && near && now - lastClickTime < NSEvent.doubleClickInterval {
            clickCount = min(clickCount + 1, 3)
        } else {
            clickCount = 1
        }
        lastClickTime = now
        lastClickPoint = p
        lastClickButton = button
        let types: [CGEventType] = button == .left ? [.leftMouseDown, .leftMouseUp] : [.rightMouseDown, .rightMouseUp]
        for type in types {
            guard let e = CGEvent(mouseEventSource: source, mouseType: type, mouseCursorPosition: p, mouseButton: button) else { continue }
            e.setIntegerValueField(.mouseEventClickState, value: Int64(clickCount))
            e.post(tap: .cghidEventTap)
        }
        clicks += 1
    }
}

// MARK: - 藍牙自動重連（背景佇列，不卡住主執行緒）

final class Reconnector {
    private let queue = DispatchQueue(label: "local.winston.airmouse.bluetooth")
    private var inFlight = false
    private var nextAttempt = 0.0
    private var failures = 0
    private let schedule: [Double] = [3, 5, 10, 20, 30]
    var onResult: (([String: Any]) -> Void)?
    var preferredAddress: (() -> String?)?

    func reset() { failures = 0; nextAttempt = 0 }
    func delay(until time: Double) { nextAttempt = max(nextAttempt, time) }

    func maybeAttempt(now: Double) {
        guard !inFlight, now >= nextAttempt else { return }
        inFlight = true
        let preferred = preferredAddress?()
        queue.async {
            let result = Reconnector.attempt(preferred: preferred)
            DispatchQueue.main.async {
                self.inFlight = false
                let ok = (result["result"] as? String) == "connected" || (result["result"] as? String) == "already_connected"
                self.failures = ok ? 0 : self.failures + 1
                // 連續失敗很多次（例如耳機正被 iPhone 使用）就放慢到每分鐘一次
                let wait = self.failures > 10 ? 60 : self.schedule[min(self.failures, self.schedule.count - 1)]
                self.nextAttempt = uptime() + wait
                var r = result
                r["nextAttemptSeconds"] = wait
                self.onResult?(r)
            }
        }
    }

    /// 找出目前已連線的 AirPods 位址，供之後重連優先使用。
    func learnConnectedAddress(_ completion: @escaping (String) -> Void) {
        queue.async {
            let connected = Reconnector.airPods().filter { $0.isConnected() }
            guard connected.count == 1, let address = connected[0].addressString else { return }
            DispatchQueue.main.async { completion(address) }
        }
    }

    private static func airPods() -> [IOBluetoothDevice] {
        let paired = (IOBluetoothDevice.pairedDevices() as? [IOBluetoothDevice]) ?? []
        return paired.filter { ($0.name ?? "").localizedCaseInsensitiveContains("AirPods") }
    }

    private static func attempt(preferred: String?) -> [String: Any] {
        let candidates = airPods()
        guard !candidates.isEmpty else { return ["result": "no_airpods_paired"] }
        let target = candidates.first(where: { preferred != nil && $0.addressString == preferred })
            ?? candidates.max(by: { ($0.recentAccessDate() ?? .distantPast) < ($1.recentAccessDate() ?? .distantPast) })
        guard let device = target else { return ["result": "no_target"] }
        if device.isConnected() { return ["result": "already_connected", "candidates": candidates.count] }
        let started = uptime()
        let status = device.openConnection()
        return ["result": status == kIOReturnSuccess ? "connected" : "failed",
                "ioReturn": Int(status),
                "seconds": uptime() - started,
                "candidates": candidates.count]
    }
}

// MARK: - 方向校正：先靜止取重力，再抬起前端取左右軸

final class Calibrator {
    enum Phase { case still, waitLift, lifting, done }
    let source: Int
    private(set) var phase = Phase.still
    private var start: Double?
    private var gSum = V3.zero, wSum = 0.0, wMax = 0.0, n = 0
    private var up = V3.zero
    private var integral = V3.zero, lastT = 0.0, moveStart = 0.0
    private var calmSince: Double?
    private let onUpdate: (String, String) -> Void
    private let onFinish: (V3?, String) -> Void

    init(source: Int, onUpdate: @escaping (String, String) -> Void, onFinish: @escaping (V3?, String) -> Void) {
        self.source = source
        self.onUpdate = onUpdate
        self.onFinish = onFinish
    }

    private func restartStill(_ reason: String) {
        phase = .still
        start = nil
        gSum = .zero; wSum = 0; wMax = 0; n = 0
        onUpdate("第 1 步：前端對著螢幕，拿穩不動", reason)
    }

    func process(t: Double, w: V3, g: V3) {
        switch phase {
        case .still:
            if start == nil { start = t }
            gSum = gSum + g
            wSum += w.length
            wMax = max(wMax, w.length)
            n += 1
            if wMax > 0.6 { restartStill("動作太大了，請拿穩，重新計時中…"); return }
            guard let s = start, t - s >= 1.5 else { return }
            guard wSum / Double(n) < 0.2, let u = (gSum * (-1.0 / Double(n))).unit else {
                restartStill("還在晃動，請拿穩，重新計時中…"); return
            }
            up = u
            phase = .waitLift
            start = t
            onUpdate("第 2 步：把盒子前端往上抬約 30°，然後停住",
                     "像手電筒從照地板改成照前方那樣，只往上抬，不要左右轉。")
        case .waitLift:
            if w.length > 0.4 {
                phase = .lifting
                integral = w * 0.02
                lastT = t
                moveStart = t
                calmSince = nil
            } else if let s = start, t - s > 8 {
                finish(nil, "沒有偵測到抬起的動作，請再試一次。")
            }
        case .lifting:
            let dt = min(max(t - lastT, 0), 0.1)
            lastT = t
            integral = integral + w * dt
            if w.length < 0.25 {
                if calmSince == nil { calmSince = t }
                if let c = calmSince, t - c >= 0.3 { complete(); return }
            } else {
                calmSince = nil
            }
            if t - moveStart > 5 { complete() }
        case .done:
            break
        }
    }

    private func complete() {
        // 積分得到的轉動向量去掉垂直分量，就是「左右軸」；抬起前端＝繞左右軸正向轉動。
        let horizontal = integral - up * integral.dot(up)
        let degrees = horizontal.length * 180 / .pi
        guard horizontal.length >= 0.26, let right = horizontal.unit, let forward = up.cross(right).unit else {
            finish(nil, String(format: "只抬了約 %.0f°，請抬到約 30° 再試一次。", degrees))
            return
        }
        finish(forward, String(format: "抬起約 %.0f°。", degrees))
    }

    private func finish(_ forward: V3?, _ message: String) {
        phase = .done
        onFinish(forward, message)
    }
}

// MARK: - 校正視窗

final class CalibrationPanel: NSObject, NSWindowDelegate {
    enum State { case idle, running, success, failed }
    let window: NSPanel
    private let headline = NSTextField(wrappingLabelWithString: "")
    private let detail = NSTextField(wrappingLabelWithString: "")
    private let primary = NSButton(title: "開始校正", target: nil, action: nil)
    private(set) var state = State.idle
    var onStart: (() -> Void)?
    var onClose: (() -> Void)?

    override init() {
        window = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 480, height: 240),
                         styleMask: [.titled, .closable], backing: .buffered, defer: false)
        super.init()
        window.title = "校正方向"
        window.level = .floating
        window.isReleasedWhenClosed = false
        // 選單列 App 常常不是前景 App；NSPanel 預設失焦就隱藏，會讓校正視窗看不到。
        window.hidesOnDeactivate = false
        window.delegate = self
        headline.font = .systemFont(ofSize: 17, weight: .semibold)
        detail.font = .systemFont(ofSize: 13)
        detail.textColor = .secondaryLabelColor
        headline.preferredMaxLayoutWidth = 440
        detail.preferredMaxLayoutWidth = 440
        primary.target = self
        primary.action = #selector(primaryPressed)
        primary.keyEquivalent = "\r"
        primary.bezelStyle = .rounded
        let stack = NSStackView(views: [headline, detail, primary])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 14
        stack.edgeInsets = NSEdgeInsets(top: 20, left: 20, bottom: 20, right: 20)
        stack.translatesAutoresizingMaskIntoConstraints = false
        let content = NSView()
        content.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: content.leadingAnchor),
            stack.trailingAnchor.constraint(equalTo: content.trailingAnchor),
            stack.topAnchor.constraint(equalTo: content.topAnchor),
            stack.bottomAnchor.constraint(lessThanOrEqualTo: content.bottomAnchor),
            content.widthAnchor.constraint(equalToConstant: 480),
        ])
        window.contentView = content
    }

    func show(intro: String) {
        update("校正 AirPods 空中滑鼠", intro, state: .idle)
        window.center()
        window.makeKeyAndOrderFront(nil)
        window.orderFrontRegardless()
    }

    func update(_ title: String, _ text: String, state: State) {
        headline.stringValue = title
        detail.stringValue = text
        self.state = state
        switch state {
        case .idle: primary.title = "開始校正"
        case .running: primary.title = "重新開始"
        case .success: primary.title = "完成"
        case .failed: primary.title = "再試一次"
        }
        window.layoutIfNeeded()
        if let size = window.contentView?.fittingSize {
            window.setContentSize(NSSize(width: 480, height: max(size.height, 160)))
        }
    }

    @objc private func primaryPressed() {
        if state == .success { window.close() } else { onStart?() }
    }

    func windowWillClose(_ notification: Notification) { onClose?() }
}

// MARK: - 點按偵測（即時使用與校正分析共用同一套規則）

struct TapParams {
    var threshold: Double              // g：加速度單點尖峰門檻
    var noiseMultiplier = 5.0          // 門檻至少是最近晃動程度的幾倍（手越晃門檻越高）
    var refractory = 0.14              // 秒：點按後約 0.1 秒的「回彈」不算第二下
    var quietW = 1.2, quietA = 0.35    // 尖峰前兩點不能在揮動
    var subtleBelow = 0.30             // 比這弱的點按，要求先靜止約 0.3 秒
    var stillCount = 15
    var stillW = 0.8, stillA = 0.2
    var doubleWindow = 0.6             // 上一下之後這段時間內，第二下不要求先靜止（雙擊）
    var rotPeak = 1.4, rotSharp = 1.1, rotDecay = 0.65   // 敲側邊時的轉速尖峰
}

final class TapDetector {
    var params: TapParams
    private var ws: [V3] = []
    private var accs: [V3] = []
    private var sharpHistory: [Double] = []
    private var lastTap = -10.0

    init(params: TapParams) { self.params = params }

    func reset() {
        ws.removeAll()
        accs.removeAll()
        sharpHistory.removeAll()
    }

    private func noiseLevel() -> Double {
        guard sharpHistory.count >= 10 else { return 0.02 }
        let sorted = sharpHistory.sorted()
        return sorted[sorted.count / 2]
    }

    /// 送入一筆新資料；回傳值代表「上一筆」是點按（要看到下一筆才知道尖峰有沒有立刻消失，約晚 20 毫秒）。
    func feed(w next: V3, a nextA: V3, t: Double) -> [String: Any]? {
        defer {
            ws.append(next)
            accs.append(nextA)
            let keep = params.stillCount + 3
            if ws.count > keep { ws.removeFirst(ws.count - keep) }
            if accs.count > keep { accs.removeFirst(accs.count - keep) }
        }
        guard ws.count >= 3 else { return nil }
        let c = ws.count - 1
        let wc = ws[c], w1 = ws[c - 1], w2 = ws[c - 2]
        let ac = accs[c], a1 = accs[c - 1], a2 = accs[c - 2]
        let sharpA = (ac - (a1 + nextA) * 0.5).length
        let sharpW = (wc - (w1 + next) * 0.5).length
        let noise = noiseLevel()
        sharpHistory.append(sharpA)
        if sharpHistory.count > 50 { sharpHistory.removeFirst() }

        guard t - lastTap >= params.refractory else { return nil }
        let quietW = max(w2.length, w1.length)
        let quietA = max(a2.length, a1.length)
        guard quietW <= params.quietW, quietA <= params.quietA else { return nil }

        let peakW = wc.length
        let rot = peakW >= params.rotPeak && peakW > w1.length && peakW >= next.length
            && next.length <= params.rotDecay * peakW && sharpW >= params.rotSharp

        let threshold = max(params.threshold, params.noiseMultiplier * noise)
        var acc = sharpA >= threshold && ac.length >= a1.length && ac.length >= nextA.length
        if acc && sharpA < params.subtleBelow && t - lastTap > params.doubleWindow {
            let start = c - params.stillCount
            if start < 0 {
                acc = false
            } else {
                for i in start..<(c - 1) where ws[i].length > params.stillW || accs[i].length > params.stillA {
                    acc = false
                    break
                }
            }
        }
        guard acc || rot else { return nil }
        lastTap = t
        return ["kind": rot ? (acc ? "both" : "rotation") : "accel",
                "sharpA": sharpA, "sharpW": sharpW, "peakA": ac.length, "peakW": peakW,
                "noise": noise, "threshold": threshold, "quietW": quietW, "quietA": quietA]
    }
}

// MARK: - 點按校正測試：依提示點按，取得「哪一下是真的按」的標準答案

final class TapTestSession {
    enum Kind: String { case still, single, double, move }
    struct Step { let kind: Kind; let title: String; let detail: String; let duration: Double; let interval: Double; let count: Int }
    struct Segment { let kind: Kind; let start: Double; var end: Double; var prompts: [Double] }
    struct Sample { let t: Double; let w: V3; let a: V3 }

    let steps: [Step] = [
        Step(kind: .still, title: "1／4　拿穩，不要按",
             detail: "像平常使用時一樣拿著打開的盒子，保持不動 8 秒。這一步是量你的手本身有多晃。",
             duration: 8, interval: 0, count: 0),
        Step(kind: .single, title: "2／4　圓點變綠就按一下",
             detail: "用你希望的「最輕」力道點按盒子一下。共 10 次。",
             duration: 0, interval: 1.7, count: 10),
        Step(kind: .double, title: "3／4　圓點變綠就快速按兩下",
             detail: "像滑鼠雙擊一樣，快速連按兩下。共 5 次。",
             duration: 0, interval: 2.5, count: 5),
        Step(kind: .move, title: "4／4　正常移動，不要按",
             detail: "像在移動游標一樣左右、上下轉動盒子，偶爾停一下，但完全不要按。15 秒。",
             duration: 15, interval: 0, count: 0),
    ]
    private(set) var samples: [Sample] = []
    private(set) var segments: [Segment] = []
    var onUpdate: ((String, String, Bool, String) -> Void)?
    var onEvent: ((String, [String: Any]) -> Void)?
    var onFinish: ((TapTestSession) -> Void)?
    private var timer: Timer?
    private var index = -1
    private var prepUntil = 0.0
    private var running = false
    private var stepStart = 0.0
    private var nextPrompt = 0

    func start() {
        let t = Timer(timeInterval: 0.03, repeats: true) { [weak self] _ in self?.tick() }
        RunLoop.main.add(t, forMode: .common)
        timer = t
        advance()
    }

    func cancel() {
        timer?.invalidate()
        timer = nil
    }

    func feed(t: Double, w: V3, a: V3) {
        if index >= 0 && index < steps.count { samples.append(Sample(t: t, w: w, a: a)) }
    }

    private func advance() {
        index += 1
        guard index < steps.count else {
            cancel()
            onFinish?(self)
            return
        }
        running = false
        prepUntil = uptime() + 3
    }

    private func promptTime(_ i: Int, _ step: Step) -> Double { stepStart + 1.0 + Double(i) * step.interval }

    private func tick() {
        guard index >= 0, index < steps.count else { return }
        let step = steps[index]
        let now = uptime()
        if !running {
            let remaining = prepUntil - now
            if remaining > 0 {
                onUpdate?(step.title, step.detail, false, "\(Int(remaining.rounded(.up))) 秒後開始…")
                return
            }
            running = true
            stepStart = now
            nextPrompt = 0
            segments.append(Segment(kind: step.kind, start: now, end: now, prompts: []))
            onEvent?("tap_test_step", ["kind": step.kind.rawValue, "phase": "start"])
        }
        let last = segments.count - 1
        switch step.kind {
        case .still, .move:
            let left = step.duration - (now - stepStart)
            onUpdate?(step.title, step.detail, false, "剩 \(max(0, Int(left.rounded(.up)))) 秒")
            if left <= 0 { endStep() }
        case .single, .double:
            while nextPrompt < step.count && now >= promptTime(nextPrompt, step) {
                segments[last].prompts.append(promptTime(nextPrompt, step))
                onEvent?("tap_test_prompt", ["kind": step.kind.rawValue, "index": nextPrompt])
                nextPrompt += 1
            }
            let lit = segments[last].prompts.last.map { now - $0 < 0.45 } ?? false
            onUpdate?(step.title, step.detail, lit, "\(segments[last].prompts.count) / \(step.count)")
            if nextPrompt >= step.count && now >= promptTime(step.count - 1, step) + step.interval { endStep() }
        }
    }

    private func endStep() {
        segments[segments.count - 1].end = uptime()
        onEvent?("tap_test_step", ["kind": steps[index].kind.rawValue, "phase": "end"])
        advance()
    }
}

struct TapTestRow {
    let threshold: Double
    let singleHits: Int, singleTotal: Int
    let doubleOK: Int, doubleTotal: Int
    let extra: Int          // 按一下卻多算（會變成雙擊）
    let falseStill: Int, falseMove: Int
    var falseTotal: Int { falseStill + falseMove }
    var cost: Double { 4 * Double(falseTotal) + 2 * Double(extra) + Double(singleTotal - singleHits) + Double(doubleTotal - doubleOK) }
}

struct TapTestResult {
    let rows: [TapTestRow]
    let best: TapTestRow?
    let stillNoise: Double              // 靜止時的晃動（第 95 百分位）
    let singleStrengths: [Double]       // 每次提示後最強的尖峰
    var logFields: [String: Any] {
        var f: [String: Any] = ["stillNoise": stillNoise, "singleStrengths": singleStrengths]
        if let b = best {
            f["best"] = ["threshold": b.threshold, "single": "\(b.singleHits)/\(b.singleTotal)",
                         "double": "\(b.doubleOK)/\(b.doubleTotal)", "extra": b.extra,
                         "falseStill": b.falseStill, "falseMove": b.falseMove]
        }
        f["rows"] = rows.map { ["t": $0.threshold, "s": $0.singleHits, "d": $0.doubleOK, "x": $0.extra, "fs": $0.falseStill, "fm": $0.falseMove] }
        return f
    }
}

enum TapTestAnalysis {
    static let thresholds: [Double] = stride(from: 0.06, through: 0.50, by: 0.02).map { ($0 * 100).rounded() / 100 }

    static func detections(_ session: TapTestSession, threshold: Double) -> [Double] {
        let detector = TapDetector(params: TapParams(threshold: threshold))
        var times: [Double] = []
        var previous: Double?
        for s in session.samples {
            if detector.feed(w: s.w, a: s.a, t: s.t) != nil { times.append(previous ?? s.t) }
            previous = s.t
        }
        return times
    }

    static func analyze(_ session: TapTestSession) -> TapTestResult {
        let rows = thresholds.map { threshold -> TapTestRow in
            let det = detections(session, threshold: threshold)
            var singleHits = 0, singleTotal = 0, doubleOK = 0, doubleTotal = 0, extra = 0, fStill = 0, fMove = 0
            for seg in session.segments {
                switch seg.kind {
                case .still:
                    fStill += det.filter { $0 >= seg.start + 0.3 && $0 <= seg.end }.count
                case .move:
                    fMove += det.filter { $0 >= seg.start + 0.3 && $0 <= seg.end }.count
                case .single, .double:
                    for (i, p) in seg.prompts.enumerated() {
                        let end = i + 1 < seg.prompts.count ? seg.prompts[i + 1] - 0.15 : seg.end
                        let n = det.filter { $0 >= p - 0.15 && $0 < end }.count
                        if seg.kind == .single {
                            singleTotal += 1
                            if n >= 1 { singleHits += 1 }
                            extra += max(0, n - 1)
                        } else {
                            doubleTotal += 1
                            if n == 2 { doubleOK += 1 }
                            extra += max(0, n - 2)
                        }
                    }
                }
            }
            return TapTestRow(threshold: threshold, singleHits: singleHits, singleTotal: singleTotal,
                              doubleOK: doubleOK, doubleTotal: doubleTotal, extra: extra,
                              falseStill: fStill, falseMove: fMove)
        }
        // 成本最低者；同分時選比較高（比較保守）的門檻
        let best = rows.min { a, b in a.cost != b.cost ? a.cost < b.cost : a.threshold > b.threshold }

        // 力道與雜訊統計（給使用者看）
        let s = session.samples
        var sharp: [(t: Double, v: Double)] = []
        if s.count >= 3 {
            for i in 1..<(s.count - 1) {
                sharp.append((s[i].t, (s[i].a - (s[i - 1].a + s[i + 1].a) * 0.5).length))
            }
        }
        var stillValues: [Double] = []
        var strengths: [Double] = []
        for seg in session.segments {
            if seg.kind == .still {
                stillValues += sharp.filter { $0.t >= seg.start + 0.3 && $0.t <= seg.end }.map { $0.v }
            } else if seg.kind == .single {
                for (i, p) in seg.prompts.enumerated() {
                    let end = i + 1 < seg.prompts.count ? seg.prompts[i + 1] - 0.15 : seg.end
                    strengths.append(sharp.filter { $0.t >= p - 0.15 && $0.t < end }.map { $0.v }.max() ?? 0)
                }
            }
        }
        stillValues.sort()
        let p95 = stillValues.isEmpty ? 0 : stillValues[min(stillValues.count - 1, Int(Double(stillValues.count) * 0.95))]
        return TapTestResult(rows: rows, best: best, stillNoise: p95, singleStrengths: strengths)
    }
}

// MARK: - 點按校正測試視窗

final class TapTestPanel: NSObject, NSWindowDelegate {
    enum Mode { case intro, running, result, message }
    let window: NSPanel
    private let headline = NSTextField(wrappingLabelWithString: "")
    private let detail = NSTextField(wrappingLabelWithString: "")
    private let dot = NSView()
    private let progress = NSTextField(labelWithString: "")
    private let resultText = NSTextField(wrappingLabelWithString: "")
    private let primary = NSButton(title: "開始測試", target: nil, action: nil)
    private let retry = NSButton(title: "重新測試", target: nil, action: nil)
    private let secondary = NSButton(title: "關閉", target: nil, action: nil)
    private var dotRow: NSStackView!
    private(set) var mode = Mode.intro
    private var suggested: Double?
    var onStart: (() -> Void)?
    var onApply: ((Double) -> Void)?
    var onClose: (() -> Void)?

    override init() {
        window = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 540, height: 300),
                         styleMask: [.titled, .closable], backing: .buffered, defer: false)
        super.init()
        window.title = "點按校正測試"
        window.level = .floating
        window.isReleasedWhenClosed = false
        window.hidesOnDeactivate = false
        window.delegate = self
        headline.font = .systemFont(ofSize: 20, weight: .semibold)
        detail.font = .systemFont(ofSize: 14)
        detail.textColor = .secondaryLabelColor
        progress.font = .monospacedDigitSystemFont(ofSize: 28, weight: .medium)
        resultText.font = .monospacedSystemFont(ofSize: 12, weight: .regular)
        for label in [headline, detail, resultText] { label.preferredMaxLayoutWidth = 500 }
        dot.wantsLayer = true
        dot.layer?.cornerRadius = 36
        dot.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([dot.widthAnchor.constraint(equalToConstant: 72), dot.heightAnchor.constraint(equalToConstant: 72)])
        setDot(false)
        dotRow = NSStackView(views: [dot, progress])
        dotRow.orientation = .horizontal
        dotRow.spacing = 20
        for (button, action) in [(primary, #selector(primaryPressed)), (retry, #selector(retryPressed)), (secondary, #selector(secondaryPressed))] {
            button.target = self
            button.action = action
            button.bezelStyle = .rounded
        }
        primary.keyEquivalent = "\r"
        let buttons = NSStackView(views: [primary, retry, secondary])
        buttons.orientation = .horizontal
        buttons.spacing = 10
        let stack = NSStackView(views: [headline, detail, dotRow, resultText, buttons])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 16
        stack.edgeInsets = NSEdgeInsets(top: 22, left: 22, bottom: 22, right: 22)
        stack.translatesAutoresizingMaskIntoConstraints = false
        let content = NSView()
        content.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: content.leadingAnchor),
            stack.trailingAnchor.constraint(equalTo: content.trailingAnchor),
            stack.topAnchor.constraint(equalTo: content.topAnchor),
            stack.bottomAnchor.constraint(lessThanOrEqualTo: content.bottomAnchor),
            content.widthAnchor.constraint(equalToConstant: 540),
        ])
        window.contentView = content
    }

    private func setDot(_ on: Bool) {
        dot.layer?.backgroundColor = (on ? NSColor.systemGreen : NSColor.tertiaryLabelColor).cgColor
    }

    private func layout(_ mode: Mode) {
        let changed = mode != self.mode
        self.mode = mode
        dotRow.isHidden = mode != .running
        resultText.isHidden = mode != .result
        retry.isHidden = mode != .result
        primary.isHidden = mode == .running
        secondary.title = mode == .running ? "取消測試" : "關閉"
        if changed || mode != .running {
            window.layoutIfNeeded()
            if let size = window.contentView?.fittingSize {
                window.setContentSize(NSSize(width: 540, height: max(size.height, 200)))
            }
        }
    }

    func showIntro(currentThreshold: Double) {
        headline.stringValue = "點按校正測試"
        detail.stringValue = String(format: """
            測試約 1 分鐘，期間游標不會動，也不會點擊。請兩耳留在盒內、盒蓋打開。
            1. 拿穩不動 8 秒
            2. 圓點變綠就用最輕的力道按一下（10 次）
            3. 圓點變綠就快速按兩下（5 次）
            4. 正常移動盒子 15 秒，不要按
            測完會自動算出抓得到你最輕的點按、又不會誤觸的門檻。目前門檻：%.2f g。
            """, currentThreshold)
        primary.title = "開始測試"
        suggested = nil
        layout(.intro)
        window.center()
        window.makeKeyAndOrderFront(nil)
        window.orderFrontRegardless()
    }

    func showMessage(_ title: String, _ text: String) {
        headline.stringValue = title
        detail.stringValue = text
        primary.title = "開始測試"
        suggested = nil
        layout(.message)
    }

    func showStep(_ title: String, _ text: String, dotOn: Bool, progress value: String) {
        if headline.stringValue != title { headline.stringValue = title }
        if detail.stringValue != text { detail.stringValue = text }
        progress.stringValue = value
        setDot(dotOn)
        layout(.running)
    }

    func showResult(_ result: TapTestResult, currentThreshold: Double) {
        guard let best = result.best else {
            showMessage("沒有收到足夠的資料", "測試期間動作資料中斷了，請確認盒蓋打開後再試一次。")
            return
        }
        suggested = best.threshold
        let strengths = result.singleStrengths.filter { $0 > 0 }.sorted()
        let strengthText = strengths.isEmpty ? "—" : String(format: "%.2f–%.2f g（中位數 %.2f g）", strengths.first!, strengths.last!, strengths[strengths.count / 2])
        headline.stringValue = String(format: "建議門檻：%.2f g", best.threshold)
        detail.stringValue = String(format: """
            用這個門檻重算這次測試：單擊 %d/%d 抓到、雙擊 %d/%d 成功、多算 %d 次、誤觸 %d 次（靜止 %d、移動 %d）。
            你的手靜止時晃動約 %.2f g；你的點按力道 %@。
            """, best.singleHits, best.singleTotal, best.doubleOK, best.doubleTotal, best.extra,
            best.falseTotal, best.falseStill, best.falseMove, result.stillNoise, strengthText)
        var lines = ["門檻     單擊    雙擊   多算  誤觸"]
        let shown = Set([0.08, 0.10, 0.12, 0.14, 0.16, 0.18, 0.20, 0.24, 0.30, 0.40, best.threshold, currentThreshold].map { ($0 * 100).rounded() / 100 })
        for row in result.rows where shown.contains(row.threshold) {
            let mark = row.threshold == best.threshold ? "  ← 建議" : (abs(row.threshold - currentThreshold) < 0.001 ? "  ← 目前" : "")
            lines.append(String(format: "%.2f g   %2d/%-2d   %d/%d    %2d    %2d%@", row.threshold, row.singleHits, row.singleTotal,
                                row.doubleOK, row.doubleTotal, row.extra, row.falseTotal, mark))
        }
        lines.append("「多算」＝按一下被算成兩下；「誤觸」＝沒按卻點了。")
        resultText.stringValue = lines.joined(separator: "\n")
        primary.title = String(format: "套用 %.2f g", best.threshold)
        layout(.result)
    }

    @objc private func primaryPressed() {
        if mode == .result, let value = suggested {
            onApply?(value)
            headline.stringValue = String(format: "已套用 %.2f g", value)
            primary.isHidden = true
        } else {
            onStart?()
        }
    }

    @objc private func retryPressed() { onStart?() }

    @objc private func secondaryPressed() {
        if mode == .running {
            onClose?()
            showMessage("已取消測試", "準備好之後再按「開始測試」。")
        } else {
            window.close()
        }
    }

    func windowWillClose(_ notification: Notification) { onClose?() }
}

// MARK: - 主控制器

final class AppDelegate: NSObject, NSApplicationDelegate, CMHeadphoneMotionManagerDelegate {
    let manager = CMHeadphoneMotionManager()
    let settings = Settings()
    let log: EventLog
    let rawLogging: Bool
    let cursor = CursorDriver()
    let reconnector = Reconnector()

    // 選單
    var statusItem: NSStatusItem!
    let menu = NSMenu()
    var statusLine: NSMenuItem!
    var sessionLine: NSMenuItem!
    var permissionItem: NSMenuItem!
    var probeItem: NSMenuItem!
    var controlItem: NSMenuItem!
    var tapItem: NSMenuItem!
    let tapCustomItem = NSMenuItem(title: "", action: nil, keyEquivalent: "")
    var invertItem: NSMenuItem!
    var reconnectItem: NSMenuItem!
    var speedItems: [NSMenuItem] = []
    var tapSensitivityItems: [NSMenuItem] = []
    var currentIcon = ""

    // 校正
    var calibrationPanel: CalibrationPanel?
    var calibrator: Calibrator?
    var promptedSources = Set<Int>()

    // 串流狀態
    var motionConnected = false
    var streamGeneration = 0
    var streamStart = 0.0
    var lastRestart = -100.0
    var lastSampleTime: Double?
    var lastSource = -1
    var lastSensorTimestamp = -1.0
    var samplesThisSecond = 0
    var hz = 0

    // 點按偵測（左鍵）與點按校正測試
    let tapDetector = TapDetector(params: TapParams(threshold: 0.30))
    var tapTest: TapTestSession?
    var tapTestPanel: TapTestPanel?

    // 本次執行統計
    let launchTime = uptime()
    var totalSamples = 0, duplicates = 0, dataSeconds = 0, interruptions = 0
    var longestGap = 0.0, cmDisconnects = 0, reconnectAttempts = 0, reconnectSuccesses = 0
    var windowSamples = 0, windowMaxGap = 0.0, ticks = 0

    var controlEnabled = true
    var accessibilityOK = false
    var probeRunning = false
    var hotKeyRef: EventHotKeyRef?

    override init() {
        let args = CommandLine.arguments.dropFirst()
        rawLogging = args.contains("--raw")
        let dir = args.first(where: { !$0.hasPrefix("-") }).map { URL(fileURLWithPath: $0, isDirectory: true) }
            ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Logs/AirPodsAirMouse", isDirectory: true)
        log = EventLog(directory: dir)
        super.init()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        log.write("launch", ["macOS": ProcessInfo.processInfo.operatingSystemVersionString,
                             "version": Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "?",
                             "rawLogging": rawLogging,
                             "calibrated": [1, 2].filter { settings.forward(for: $0) != nil }])
        buildMenu()
        cursor.gain = settings.gain
        cursor.invertY = settings.invertY
        cursor.enabled = true
        tapDetector.params.threshold = settings.tapThreshold

        accessibilityOK = AXIsProcessTrustedWithOptions(["AXTrustedCheckOptionPrompt": true] as CFDictionary)
        log.write("accessibility", ["trusted": accessibilityOK])

        reconnector.preferredAddress = { [weak self] in self?.settings.preferredAddress }
        reconnector.onResult = { [weak self] r in self?.handleReconnectResult(r) }
        reconnector.delay(until: uptime() + 3)

        manager.delegate = self
        startStream(reason: "launch")
        registerHotKey()

        let t = Timer(timeInterval: 1, repeats: true) { [weak self] _ in self?.tick() }
        RunLoop.main.add(t, forMode: .common)

        NSWorkspace.shared.notificationCenter.addObserver(self, selector: #selector(didWake), name: NSWorkspace.didWakeNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(screensChanged), name: NSApplication.didChangeScreenParametersNotification, object: nil)
        DistributedNotificationCenter.default().addObserver(self, selector: #selector(openCalibration), name: showRequest, object: nil)
        DistributedNotificationCenter.default().addObserver(self, selector: #selector(openTapTest), name: tapTestRequest, object: nil)
        if CommandLine.arguments.contains("--tap-test") {
            DispatchQueue.main.asyncAfter(deadline: .now() + 1) { self.openTapTest() }
        }
        refreshUI()
    }

    /// 再次打開 App（雙擊或 open）時顯示校正視窗，方便在選單列圖示被瀏海遮住時使用。
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        openCalibration()
        return false
    }

    func applicationWillTerminate(_ notification: Notification) {
        manager.stopDeviceMotionUpdates()
        if let ref = hotKeyRef { UnregisterEventHotKey(ref) }
        log.write("session_end", sessionSummary())
    }

    // MARK: 串流

    func startStream(reason: String) {
        streamGeneration += 1
        streamStart = uptime()
        log.write("start_stream", ["reason": reason, "generation": streamGeneration,
                                   "available": manager.isDeviceMotionAvailable,
                                   "authorization": CMHeadphoneMotionManager.authorizationStatus().rawValue])
        manager.startDeviceMotionUpdates(to: .main) { [weak self] motion, error in
            guard let self else { return }
            if let error { self.log.write("motion_error", ["message": error.localizedDescription]); return }
            if let motion { self.handle(motion) }
        }
    }

    func restartStream(reason: String) {
        manager.stopDeviceMotionUpdates()
        lastRestart = uptime()
        startStream(reason: reason)
    }

    func headphoneMotionManagerDidConnect(_ manager: CMHeadphoneMotionManager) {
        DispatchQueue.main.async {
            self.motionConnected = true
            self.log.write("connected")
            self.refreshUI()
        }
    }

    func headphoneMotionManagerDidDisconnect(_ manager: CMHeadphoneMotionManager) {
        DispatchQueue.main.async {
            self.motionConnected = false
            self.cmDisconnects += 1
            self.cursor.halt()
            self.log.write("disconnected")
            self.reconnector.reset()
            self.refreshUI()
        }
    }

    func handle(_ motion: CMDeviceMotion) {
        let source = motion.sensorLocation.rawValue
        let t = motion.timestamp
        if source == lastSource && t <= lastSensorTimestamp { duplicates += 1; return }
        let now = uptime()

        if let last = lastSampleTime {
            let gap = now - last
            windowMaxGap = max(windowMaxGap, gap)
            if gap > 1.0 {
                interruptions += 1
                longestGap = max(longestGap, gap)
                log.write("data_resumed", ["gapSeconds": gap, "source": source])
            }
            if gap > 4 { afterReconnect() }
        } else {
            log.write("first_sample", ["source": source, "secondsSinceLaunch": now - launchTime])
            afterReconnect()
        }
        lastSampleTime = now
        if source != lastSource {
            if lastSource != -1 { log.write("source_changed", ["from": lastSource, "to": source]) }
            lastSource = source
            tapDetector.reset()
            promptCalibrationIfNeeded(source)
        }
        lastSensorTimestamp = t
        samplesThisSecond += 1
        totalSamples += 1
        windowSamples += 1

        let w = V3(motion.rotationRate.x, motion.rotationRate.y, motion.rotationRate.z)
        let g = V3(motion.gravity.x, motion.gravity.y, motion.gravity.z)
        let ua = V3(motion.userAcceleration.x, motion.userAcceleration.y, motion.userAcceleration.z)
        let tap = tapDetector.feed(w: w, a: ua, t: now)

        if let test = tapTest {
            // 點按校正測試期間：只收資料，不動游標、不點擊。
            test.feed(t: now, w: w, a: ua)
            if rawLogging { log.write("sample", ["t": t, "source": source, "w": w.array, "g": g.array, "ua": ua.array]) }
            return
        }

        if let cal = calibrator {
            if source != cal.source {
                startCalibrator(source: source, note: "來源換成\(sourceName(source))了，重新開始。")
            } else {
                cal.process(t: t, w: w, g: g)
            }
            return
        }
        // 串流剛開始的前幾筆姿態融合還不穩定，先略過。
        guard now - streamStart > 0.3 else { return }
        guard let forward = settings.forward(for: source),
              let up = (g * -1).unit,
              let right = forward.cross(up).unit else {
            cursor.halt()
            return
        }
        let yaw = w.dot(up)          // 左右轉
        let pitch = w.dot(right)     // 前端上下抬
        let roll = w.dot(forward)    // 手腕扭轉：不移動游標
        let swing = (yaw * yaw + pitch * pitch).squareRoot()

        var suppress = abs(roll) > 1.2 && abs(roll) > 1.2 * swing
        if let tap {
            if controlEnabled && accessibilityOK && settings.tapClicks {
                cursor.tapClick()
                suppress = true
                log.write("tap_click", tap)
            } else {
                log.write("tap_seen", tap)
            }
        }

        if rawLogging {
            log.write("sample", ["t": t, "source": source, "w": w.array, "g": g.array, "ua": ua.array,
                                 "yaw": yaw, "pitch": pitch, "roll": roll, "suppress": suppress])
        }
        cursor.input(yawRate: yaw, pitchRate: pitch, suppress: suppress, now: now)
    }

    func afterReconnect() {
        reconnector.reset()
        reconnector.learnConnectedAddress { [weak self] address in
            guard let self, self.settings.preferredAddress != address else { return }
            self.settings.preferredAddress = address
            self.log.write("preferred_device_learned")
        }
    }

    func handleReconnectResult(_ result: [String: Any]) {
        reconnectAttempts += 1
        if (result["result"] as? String) == "connected" { reconnectSuccesses += 1 }
        log.write("reconnect_attempt", result)
    }

    // MARK: 每秒檢查

    func tick() {
        let now = uptime()
        hz = samplesThisSecond
        samplesThisSecond = 0
        if hz > 0 { dataSeconds += 1 }
        accessibilityOK = AXIsProcessTrusted()
        probeRunning = !NSRunningApplication.runningApplications(withBundleIdentifier: "local.winston.airpods-motion-probe").isEmpty

        let age = lastSampleTime.map { now - $0 } ?? .infinity
        let auth = CMHeadphoneMotionManager.authorizationStatus()
        let blocked = auth == .denied || auth == .restricted
        if !blocked {
            // 權限詢問視窗還沒回答前不要重新訂閱，以免打斷系統詢問。
            if auth == .authorized {
                if !manager.isDeviceMotionActive && now - lastRestart > 5 {
                    restartStream(reason: "inactive")
                } else if age > 4 && motionConnected && now - lastRestart > 10 {
                    restartStream(reason: "stale")   // 顯示已連線卻沒新資料：重新訂閱
                }
            }
            // 已連線只是沒資料（例如通話音訊佔用）時，重連沒有幫助，不去打擾藍牙。
            if age > 4 && !motionConnected && controlEnabled && settings.autoReconnect {
                reconnector.maybeAttempt(now: now)
            }
        }

        ticks += 1
        if ticks % 10 == 0 {
            log.write("stats", ["windowSeconds": 10, "samples": windowSamples, "hz": Double(windowSamples) / 10,
                                "maxGapMs": windowMaxGap * 1000, "connected": motionConnected,
                                "source": lastSource, "control": controlEnabled, "accessibility": accessibilityOK,
                                "duplicates": duplicates])
            windowSamples = 0
            windowMaxGap = 0
        }
        refreshUI()
    }

    func sessionSummary() -> [String: Any] {
        let run = uptime() - launchTime
        return ["runSeconds": run, "dataSeconds": dataSeconds, "coverage": run > 0 ? Double(dataSeconds) / run : 0,
                "totalSamples": totalSamples, "interruptionsOver1s": interruptions, "longestGapSeconds": longestGap,
                "motionDisconnects": cmDisconnects, "reconnectAttempts": reconnectAttempts,
                "reconnectSuccesses": reconnectSuccesses, "clicks": cursor.clicks, "duplicates": duplicates]
    }

    // MARK: 選單

    func info(_ title: String) -> NSMenuItem {
        let item = NSMenuItem(title: title, action: nil, keyEquivalent: "")
        item.isEnabled = false
        return item
    }

    func item(_ title: String, _ action: Selector, key: String = "") -> NSMenuItem {
        let item = NSMenuItem(title: title, action: action, keyEquivalent: key)
        item.target = self
        return item
    }

    func buildMenu() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        menu.autoenablesItems = false
        statusItem.menu = menu

        statusLine = info("○ 啟動中…")
        sessionLine = info("")
        permissionItem = item("⚠︎ 需要「輔助使用」權限才能移動游標…", #selector(openAccessibility))
        probeItem = info("⚠︎ 請先結束「AirPods 動作測試」App")
        controlItem = item("控制游標（⌃⌥M 切換）", #selector(toggleControl))
        tapItem = item("點按盒子＝左鍵（按兩下＝雙擊）", #selector(toggleTap))
        let tapTestItem = item("點按校正測試…", #selector(openTapTest))
        let calibrate = item("校正方向…", #selector(openCalibration))
        let speedMenu = NSMenu()
        for (i, name) in Settings.speedNames.enumerated() {
            let s = item(name, #selector(setSpeed(_:)))
            s.tag = i
            speedItems.append(s)
            speedMenu.addItem(s)
        }
        let speed = NSMenuItem(title: "游標速度", action: nil, keyEquivalent: "")
        speed.submenu = speedMenu
        let tapMenu = NSMenu()
        tapMenu.addItem(tapCustomItem)
        for (i, preset) in Settings.tapPresets.enumerated() {
            let s = item(String(format: "%@　%.2f g", preset.name, preset.value), #selector(setTapPreset(_:)))
            s.tag = i
            tapSensitivityItems.append(s)
            tapMenu.addItem(s)
        }
        let tapSensitivity = NSMenuItem(title: "點按靈敏度", action: nil, keyEquivalent: "")
        tapSensitivity.submenu = tapMenu
        invertItem = item("上下反轉", #selector(toggleInvert))
        reconnectItem = item("斷線時自動重新連線", #selector(toggleReconnect))

        for i in [statusLine!, sessionLine!, permissionItem!, probeItem!, .separator(),
                  controlItem!, tapItem!, tapSensitivity, tapTestItem, calibrate, speed, .separator(),
                  invertItem!, reconnectItem!, .separator(),
                  item("打開紀錄資料夾", #selector(openLogs)),
                  item("結束", #selector(quit), key: "q")] {
            menu.addItem(i)
        }
    }

    func setIcon(_ name: String) {
        guard name != currentIcon else { return }
        currentIcon = name
        if let image = NSImage(systemSymbolName: name, accessibilityDescription: "AirPods 空中滑鼠") {
            image.isTemplate = true
            statusItem.button?.image = image
            statusItem.button?.title = ""
        } else {
            statusItem.button?.title = "AM"
        }
    }

    func refreshUI() {
        let now = uptime()
        let age = lastSampleTime.map { now - $0 } ?? .infinity
        let auth = CMHeadphoneMotionManager.authorizationStatus()
        let live = age < 1.5
        var status: String
        var icon = "cursorarrow.slash"
        if auth == .denied || auth == .restricted {
            status = "⚠︎ 沒有「動作與健身」權限（系統設定 → 隱私權）"
        } else if live {
            status = "● 已連線 · \(sourceName(lastSource)) · \(hz) Hz"
            if settings.forward(for: lastSource) == nil { status += " · 需要校正" }
            else { icon = controlEnabled ? "cursorarrow.motionlines" : "cursorarrow" }
        } else if motionConnected {
            status = "○ 已連線，等待動作資料…"
        } else {
            status = "○ 未連線：打開充電盒蓋"
        }
        statusLine.title = status
        let run = max(now - launchTime, 1)
        sessionLine.title = String(format: "本次 %d 分 · 有資料 %.0f%% · 中斷 %d 次 · 最長 %.1f 秒",
                                   Int(run / 60), Double(dataSeconds) / run * 100, interruptions, longestGap)
        permissionItem.isHidden = accessibilityOK
        probeItem.isHidden = !probeRunning
        controlItem.state = controlEnabled ? .on : .off
        tapItem.state = settings.tapClicks ? .on : .off
        invertItem.state = settings.invertY ? .on : .off
        reconnectItem.state = settings.autoReconnect ? .on : .off
        for s in speedItems { s.state = s.tag == settings.speedIndex ? .on : .off }
        let threshold = settings.tapThreshold
        let fromTest = settings.tapThresholdFromTest
        tapCustomItem.title = fromTest ? String(format: "校正測試結果　%.2f g", threshold) : "校正測試結果（尚未測試）"
        tapCustomItem.isEnabled = fromTest
        tapCustomItem.state = fromTest ? .on : .off
        for s in tapSensitivityItems {
            s.state = !fromTest && abs(Settings.tapPresets[s.tag].value - threshold) < 0.001 ? .on : .off
        }
        setIcon(icon)
    }

    @objc func toggleControl() {
        controlEnabled.toggle()
        cursor.enabled = controlEnabled && calibrator == nil
        if controlEnabled {
            reconnector.reset()
            if !accessibilityOK { accessibilityOK = AXIsProcessTrustedWithOptions(["AXTrustedCheckOptionPrompt": true] as CFDictionary) }
        }
        log.write("control", ["enabled": controlEnabled])
        refreshUI()
    }

    @objc func toggleTap() { settings.tapClicks.toggle(); log.write("setting", ["tapClicks": settings.tapClicks]); refreshUI() }
    @objc func toggleInvert() { settings.invertY.toggle(); cursor.invertY = settings.invertY; refreshUI() }
    @objc func toggleReconnect() { settings.autoReconnect.toggle(); reconnector.reset(); refreshUI() }
    @objc func setSpeed(_ sender: NSMenuItem) {
        settings.speedIndex = sender.tag
        cursor.gain = settings.gain
        log.write("setting", ["speedIndex": sender.tag])
        refreshUI()
    }
    @objc func setTapPreset(_ sender: NSMenuItem) {
        applyTapThreshold(Settings.tapPresets[sender.tag].value, fromTest: false)
    }

    func applyTapThreshold(_ value: Double, fromTest: Bool) {
        settings.tapThreshold = value
        settings.tapThresholdFromTest = fromTest
        tapDetector.params.threshold = value
        log.write("setting", ["tapThreshold": value, "fromTest": fromTest])
        refreshUI()
    }

    // MARK: 點按校正測試

    @objc func openTapTest() {
        let panel: TapTestPanel
        if let existing = tapTestPanel {
            panel = existing
        } else {
            panel = TapTestPanel()
            panel.onStart = { [weak self] in self?.startTapTest() }
            panel.onApply = { [weak self] value in self?.applyTapThreshold(value, fromTest: true) }
            panel.onClose = { [weak self] in self?.stopTapTest() }
            tapTestPanel = panel
        }
        panel.showIntro(currentThreshold: settings.tapThreshold)
        NSApp.activate()
    }

    func startTapTest() {
        let live = lastSampleTime.map { uptime() - $0 < 1.5 } ?? false
        guard live else {
            tapTestPanel?.showMessage("還沒有收到動作資料", "請確認 AirPods 已連到這台 Mac、充電盒蓋是打開的，再按「開始測試」。")
            return
        }
        cursor.enabled = false
        let session = TapTestSession()
        session.onUpdate = { [weak self] title, detail, dotOn, progress in
            self?.tapTestPanel?.showStep(title, detail, dotOn: dotOn, progress: progress)
        }
        session.onEvent = { [weak self] type, fields in self?.log.write(type, fields) }
        session.onFinish = { [weak self] session in self?.finishTapTest(session) }
        tapTest = session
        log.write("tap_test_start", ["currentThreshold": settings.tapThreshold])
        session.start()
    }

    func finishTapTest(_ session: TapTestSession) {
        tapTest = nil
        cursor.enabled = controlEnabled
        let result = TapTestAnalysis.analyze(session)
        log.write("tap_test_result", result.logFields)
        tapTestPanel?.showResult(result, currentThreshold: settings.tapThreshold)
    }

    func stopTapTest() {
        if let session = tapTest {
            session.cancel()
            log.write("tap_test_cancelled")
        }
        tapTest = nil
        cursor.enabled = controlEnabled && calibrator == nil
    }
    @objc func openLogs() { NSWorkspace.shared.open(log.directory) }
    @objc func openAccessibility() {
        _ = AXIsProcessTrustedWithOptions(["AXTrustedCheckOptionPrompt": true] as CFDictionary)
        if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility") {
            NSWorkspace.shared.open(url)
        }
    }
    @objc func quit() { NSApp.terminate(nil) }

    @objc func didWake() {
        log.write("host_did_wake")
        reconnector.reset()
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { self.restartStream(reason: "wake") }
    }

    @objc func screensChanged() { cursor.refreshDisplays() }

    // MARK: 校正流程

    func promptCalibrationIfNeeded(_ source: Int) {
        guard settings.forward(for: source) == nil, calibrator == nil, !promptedSources.contains(source) else { return }
        promptedSources.insert(source)
        DispatchQueue.main.async { self.openCalibration() }
    }

    @objc func openCalibration() {
        let panel: CalibrationPanel
        if let existing = calibrationPanel {
            panel = existing
        } else {
            panel = CalibrationPanel()
            panel.onStart = { [weak self] in self?.beginCalibration() }
            panel.onClose = { [weak self] in self?.endCalibration() }
            calibrationPanel = panel
        }
        let live = lastSampleTime.map { uptime() - $0 < 1.5 } ?? false
        let sourceText = live ? "目前資料來自\(sourceName(lastSource))。" : "目前還沒有收到動作資料，請先打開盒蓋。"
        panel.show(intro: """
            1. 兩耳留在充電盒裡、盒蓋打開，像拿遙控器一樣讓盒子前端對著螢幕。
            2. 按「開始校正」後先拿穩約 1.5 秒，再把前端往上抬約 30° 並停住。
            \(sourceText)左右耳在盒內的方向不同，各需要校正一次，之後會記住。
            """)
        NSApp.activate()
    }

    func beginCalibration() {
        let live = lastSampleTime.map { uptime() - $0 < 1.5 } ?? false
        guard live else {
            calibrationPanel?.update("還沒有收到動作資料", "請確認 AirPods 已連到這台 Mac，而且充電盒蓋是打開的。", state: .failed)
            return
        }
        startCalibrator(source: lastSource, note: "正在校正\(sourceName(lastSource))…")
    }

    func startCalibrator(source: Int, note: String) {
        cursor.enabled = false
        log.write("calibration_start", ["source": source])
        calibrator = Calibrator(source: source, onUpdate: { [weak self] title, text in
            self?.calibrationPanel?.update(title, text, state: .running)
        }, onFinish: { [weak self] forward, message in
            self?.finishCalibration(source: source, forward: forward, message: message)
        })
        calibrationPanel?.update("第 1 步：前端對著螢幕，拿穩不動", note, state: .running)
    }

    func finishCalibration(source: Int, forward: V3?, message: String) {
        calibrator = nil
        cursor.enabled = controlEnabled
        if let forward {
            settings.setForward(forward, for: source)
            log.write("calibration_done", ["source": source, "forward": forward.array])
            calibrationPanel?.update("校正完成（\(sourceName(source))）", """
                \(message)
                左右轉動盒子＝游標左右，前端上下抬＝游標上下。
                停住後點按盒子＝左鍵，快速按兩下＝雙擊。⌃⌥M 可暫停／恢復控制。
                想抓更細微的點按，請從選單執行「點按校正測試」。
                """, state: .success)
        } else {
            log.write("calibration_failed", ["source": source, "message": message])
            calibrationPanel?.update("這次沒有校正成功", message, state: .failed)
        }
    }

    func endCalibration() {
        if calibrator != nil { log.write("calibration_cancelled") }
        calibrator = nil
        cursor.enabled = controlEnabled
    }

    // MARK: 全域快捷鍵 ⌃⌥M

    func registerHotKey() {
        var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
        let me = Unmanaged.passUnretained(self).toOpaque()
        InstallEventHandler(GetApplicationEventTarget(), { _, _, userData in
            guard let userData else { return noErr }
            let delegate = Unmanaged<AppDelegate>.fromOpaque(userData).takeUnretainedValue()
            DispatchQueue.main.async { delegate.toggleControl() }
            return noErr
        }, 1, &spec, me, nil)
        let id = EventHotKeyID(signature: OSType(0x414D_4F55), id: 1)
        let status = RegisterEventHotKey(UInt32(kVK_ANSI_M), UInt32(controlKey | optionKey), id,
                                         GetApplicationEventTarget(), 0, &hotKeyRef)
        log.write("hotkey", ["registered": status == noErr, "status": Int(status)])
    }
}

// MARK: - 進入點

let showRequest = Notification.Name("local.winston.airmouse.show")
let tapTestRequest = Notification.Name("local.winston.airmouse.taptest")

if let id = Bundle.main.bundleIdentifier,
   NSRunningApplication.runningApplications(withBundleIdentifier: id).contains(where: { $0.processIdentifier != getpid() }) {
    // 已經有一份在執行：請它顯示校正視窗（或加 --tap-test 顯示點按校正測試），然後自己結束。
    let request = CommandLine.arguments.contains("--tap-test") ? tapTestRequest : showRequest
    DistributedNotificationCenter.default().postNotificationName(request, object: nil, userInfo: nil, deliverImmediately: true)
    usleep(200_000)
    exit(0)
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
