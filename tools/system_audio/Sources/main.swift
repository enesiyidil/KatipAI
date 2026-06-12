import AVFoundation
import CoreMedia
import Foundation
import ScreenCaptureKit

@available(macOS 13.0, *)
final class AudioCaptureDelegate: NSObject, SCStreamOutput {
    private let stdout = FileHandle.standardOutput
    private var converter: AVAudioConverter?
    private let targetFormat = AVAudioFormat(
        commonFormat: .pcmFormatFloat32,
        sampleRate: 16000,
        channels: 1,
        interleaved: false
    )!

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
        stdout.write(Data(bytes: channelData, count: byteCount))
    }
}

@available(macOS 13.0, *)
func runCapture() throws {
    let sem = DispatchSemaphore(value: 0)
    Task {
        do {
            let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
            guard let display = content.displays.first else {
                fputs("No display found\n", stderr)
                exit(1)
            }

            let filter = SCContentFilter(display: display, excludingWindows: [])
            let config = SCStreamConfiguration()
            config.capturesAudio = true
            config.sampleRate = 48000
            config.channelCount = 2
            config.excludesCurrentProcessAudio = true

            let stream = SCStream(filter: filter, configuration: config, delegate: nil)
            let delegate = AudioCaptureDelegate()
            try stream.addStreamOutput(
                delegate, type: .audio,
                sampleHandlerQueue: DispatchQueue(label: "katipai.audio")
            )
            try await stream.startCapture()
            sem.signal()
            dispatchMain()
        } catch {
            fputs("Capture error: \(error)\n", stderr)
            exit(1)
        }
    }
    sem.wait()
}

if #available(macOS 13.0, *) {
    do {
        try runCapture()
    } catch {
        fputs("Error: \(error)\n", stderr)
        exit(1)
    }
} else {
    fputs("macOS 13+ required\n", stderr)
    exit(1)
}
