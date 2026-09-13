import AVFoundation
import CoreMedia
import Foundation
import ScreenCaptureKit
import Darwin

@available(macOS 13.0, *)
struct AppInfo: Codable {
    let bundle_id: String
    let name: String
    let pid: Int32
}

@available(macOS 13.0, *)
func logErr(_ message: String) {
    fputs(message + "\n", stderr)
    fflush(stderr)
}

@available(macOS 13.0, *)
func listAppsJSON() async throws -> String {
    let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
    var apps: [AppInfo] = []
    var seen = Set<String>()
    for app in content.applications {
        let bid = app.bundleIdentifier
        guard !bid.isEmpty, !seen.contains(bid) else { continue }
        seen.insert(bid)
        apps.append(AppInfo(bundle_id: bid, name: app.applicationName, pid: app.processID))
    }
    apps.sort { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    let data = try JSONEncoder().encode(apps)
    return String(data: data, encoding: .utf8) ?? "[]"
}

@available(macOS 13.0, *)
func connectUnixSocket(path: String) -> FileHandle? {
    let fd = socket(AF_UNIX, SOCK_STREAM, 0)
    guard fd >= 0 else { return nil }

    var addr = sockaddr_un()
    addr.sun_family = sa_family_t(AF_UNIX)
    let maxLen = MemoryLayout.size(ofValue: addr.sun_path)
    guard path.utf8.count < maxLen else {
        close(fd)
        return nil
    }
    _ = withUnsafeMutablePointer(to: &addr.sun_path.0) { ptr in
        path.withCString { cstr in
            strncpy(ptr, cstr, maxLen - 1)
        }
    }

    let size = socklen_t(MemoryLayout<sockaddr_un>.size)
    let ok = withUnsafePointer(to: &addr) { ptr in
        ptr.withMemoryRebound(to: sockaddr.self, capacity: 1) { sa in
            connect(fd, sa, size)
        }
    }
    guard ok == 0 else {
        close(fd)
        return nil
    }
    return FileHandle(fileDescriptor: fd, closeOnDealloc: true)
}

@available(macOS 13.0, *)
final class AudioCaptureDelegate: NSObject, SCStreamOutput {
    private let sink: FileHandle
    private var converter: AVAudioConverter?
    private let targetFormat = AVAudioFormat(
        commonFormat: .pcmFormatFloat32,
        sampleRate: 16000,
        channels: 1,
        interleaved: false
    )!

    init(sink: FileHandle) {
        self.sink = sink
    }

    func stream(_ stream: SCStream, didOutputSampleBuffer sampleBuffer: CMSampleBuffer, of type: SCStreamOutputType) {
        guard type == .audio, CMSampleBufferDataIsReady(sampleBuffer) else { return }
        guard let block = CMSampleBufferGetDataBuffer(sampleBuffer) else { return }

        var length = 0
        var dataPointer: UnsafeMutablePointer<Int8>?
        CMBlockBufferGetDataPointer(
            block, atOffset: 0, lengthAtOffsetOut: nil, totalLengthOut: &length,
            dataPointerOut: &dataPointer
        )
        guard let dataPointer else { return }

        let formatDesc = CMSampleBufferGetFormatDescription(sampleBuffer)!
        guard let asbdPtr = CMAudioFormatDescriptionGetStreamBasicDescription(formatDesc) else { return }
        guard let sourceFormat = AVAudioFormat(streamDescription: asbdPtr) else { return }

        if converter == nil {
            converter = AVAudioConverter(from: sourceFormat, to: targetFormat)
        }
        guard let converter else { return }

        let frameCount = CMSampleBufferGetNumSamples(sampleBuffer)
        guard let sourceBuffer = AVAudioPCMBuffer(
            pcmFormat: sourceFormat, frameCapacity: AVAudioFrameCount(frameCount)
        ) else { return }
        sourceBuffer.frameLength = AVAudioFrameCount(frameCount)

        let audioBufferList = sourceBuffer.mutableAudioBufferList
        memcpy(audioBufferList.pointee.mBuffers.mData, dataPointer, length)

        let capacity = AVAudioFrameCount(Double(frameCount) * targetFormat.sampleRate / sourceFormat.sampleRate) + 1024
        guard let destBuffer = AVAudioPCMBuffer(pcmFormat: targetFormat, frameCapacity: capacity) else { return }

        var error: NSError?
        let inputBlock: AVAudioConverterInputBlock = { _, outStatus in
            outStatus.pointee = .haveData
            return sourceBuffer
        }
        converter.convert(to: destBuffer, error: &error, withInputFrom: inputBlock)
        guard error == nil, let channelData = destBuffer.floatChannelData?[0] else { return }

        let byteCount = Int(destBuffer.frameLength) * MemoryLayout<Float32>.size
        sink.write(Data(bytes: channelData, count: byteCount))
    }
}

@available(macOS 13.0, *)
final class CaptureSession {
    static var stream: SCStream?
    static var delegate: AudioCaptureDelegate?
}

@available(macOS 13.0, *)
func runCapture(allAudio: Bool, bundleIds: [String], socketPath: String?) async throws {
    let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
    guard let display = content.displays.first else {
        logErr("No display found")
        exit(1)
    }

    let filter: SCContentFilter
    if allAudio {
        filter = SCContentFilter(display: display, excludingWindows: [])
    } else {
        let selected = Set(bundleIds)
        let apps = content.applications.filter { selected.contains($0.bundleIdentifier) }
        if apps.isEmpty {
            logErr("No matching applications for capture")
            exit(1)
        }
        let names = apps.map { $0.applicationName }.joined(separator: ", ")
        logErr("Capturing audio from: \(names)")
        filter = SCContentFilter(display: display, including: apps, exceptingWindows: [])
    }

    let sink: FileHandle
    if let socketPath {
        guard let handle = connectUnixSocket(path: socketPath) else {
            logErr("Failed to connect socket: \(socketPath)")
            exit(1)
        }
        sink = handle
    } else {
        sink = FileHandle.standardOutput
    }

    let config = SCStreamConfiguration()
    config.capturesAudio = true
    config.sampleRate = 48000
    config.channelCount = 2
    config.excludesCurrentProcessAudio = true

    let stream = SCStream(filter: filter, configuration: config, delegate: nil)
    let delegate = AudioCaptureDelegate(sink: sink)
    CaptureSession.stream = stream
    CaptureSession.delegate = delegate
    try stream.addStreamOutput(
        delegate, type: .audio,
        sampleHandlerQueue: DispatchQueue(label: "katipai.audio")
    )
    try await stream.startCapture()
    logErr("Capture started")
}

@available(macOS 13.0, *)
func mainAsync() async throws {
    let args = CommandLine.arguments

    if args.contains("--list-apps") {
        let json = try await listAppsJSON()
        print(json)
        exit(0)
    }

    var socketPath: String?
    if let idx = args.firstIndex(of: "--socket"), idx + 1 < args.count {
        socketPath = args[idx + 1]
    }

    if args.contains("--capture") {
        let allAudio = args.contains("--all")
        var bundleIds: [String] = []
        if let idx = args.firstIndex(of: "--apps"), idx + 1 < args.count {
            bundleIds = args[idx + 1].split(separator: ",").map(String.init).filter { !$0.isEmpty }
        }
        if !allAudio && bundleIds.isEmpty {
            logErr("No apps specified. Use --all or --apps bundle.id,...")
            exit(1)
        }
        try await runCapture(allAudio: allAudio, bundleIds: bundleIds, socketPath: socketPath)
        return
    }

    try await runCapture(allAudio: true, bundleIds: [], socketPath: socketPath)
}

if #available(macOS 13.0, *) {
    Task {
        do {
            try await mainAsync()
        } catch {
            logErr("Error: \(error)")
            exit(1)
        }
    }
    dispatchMain()
} else {
    fputs("macOS 13+ required\n", stderr)
    exit(1)
}
