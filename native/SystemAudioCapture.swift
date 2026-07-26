import AVFoundation
import CoreMedia
import Foundation
import ScreenCaptureKit

private final class AudioStreamOutput: NSObject, SCStreamOutput, SCStreamDelegate {
    private let targetFormat: AVAudioFormat
    private let writeQueue = DispatchQueue(label: "com.realtimesubtitle.system-audio.write")
    private var converter: AVAudioConverter?
    private var converterInputFormat: AVAudioFormat?

    init(sampleRate: Double) {
        self.targetFormat = AVAudioFormat(
            standardFormatWithSampleRate: sampleRate,
            channels: 1
        )!
        super.init()
    }

    func stream(
        _ stream: SCStream,
        didOutputSampleBuffer sampleBuffer: CMSampleBuffer,
        of outputType: SCStreamOutputType
    ) {
        guard outputType == .audio, sampleBuffer.isValid,
              let description = sampleBuffer.formatDescription,
              let inputBuffer = AVAudioPCMBuffer(
                  pcmFormat: AVAudioFormat(cmAudioFormatDescription: description),
                  frameCapacity: AVAudioFrameCount(sampleBuffer.numSamples)
              ) else { return }

        let inputFormat = inputBuffer.format

        inputBuffer.frameLength = AVAudioFrameCount(sampleBuffer.numSamples)
        let copyStatus = CMSampleBufferCopyPCMDataIntoAudioBufferList(
            sampleBuffer,
            at: 0,
            frameCount: Int32(sampleBuffer.numSamples),
            into: inputBuffer.mutableAudioBufferList
        )
        guard copyStatus == noErr else { return }

        if converter == nil || converterInputFormat != inputFormat {
            converter = AVAudioConverter(from: inputFormat, to: targetFormat)
            converterInputFormat = inputFormat
        }
        guard let converter else { return }

        let ratio = targetFormat.sampleRate / inputFormat.sampleRate
        let capacity = max(1, AVAudioFrameCount(Double(inputBuffer.frameLength) * ratio) + 32)
        guard let outputBuffer = AVAudioPCMBuffer(
            pcmFormat: targetFormat,
            frameCapacity: capacity
        ) else { return }

        var supplied = false
        var conversionError: NSError?
        let status = converter.convert(to: outputBuffer, error: &conversionError) {
            _, inputStatus in
            if supplied {
                inputStatus.pointee = .noDataNow
                return nil
            }
            supplied = true
            inputStatus.pointee = .haveData
            return inputBuffer
        }
        guard status != .error, conversionError == nil,
              outputBuffer.frameLength > 0,
              let channel = outputBuffer.floatChannelData?[0] else { return }

        let data = Data(
            bytes: channel,
            count: Int(outputBuffer.frameLength) * MemoryLayout<Float>.size
        )
        writeQueue.async {
            FileHandle.standardOutput.write(data)
        }
    }

    func stream(_ stream: SCStream, didStopWithError error: Error) {
        FileHandle.standardError.write(
            Data("System audio stopped: \(error.localizedDescription)\n".utf8)
        )
        exit(4)
    }
}

@main
private enum SystemAudioCaptureMain {
    static func main() async {
        let arguments = CommandLine.arguments
        let sampleRate: Double
        if let index = arguments.firstIndex(of: "--sample-rate"),
           arguments.indices.contains(index + 1),
           let value = Double(arguments[index + 1]) {
            sampleRate = value
        } else {
            sampleRate = 16_000
        }

        do {
            let content = try await SCShareableContent.excludingDesktopWindows(
                false,
                onScreenWindowsOnly: false
            )
            guard let display = content.displays.first else {
                throw NSError(
                    domain: "RealtimeSubtitle",
                    code: 1,
                    userInfo: [NSLocalizedDescriptionKey: "No display is available for system audio capture."]
                )
            }

            let excluded = content.applications.filter {
                $0.bundleIdentifier == "com.realtimesubtitle.app"
            }
            let filter = SCContentFilter(
                display: display,
                excludingApplications: excluded,
                exceptingWindows: []
            )
            let configuration = SCStreamConfiguration()
            configuration.capturesAudio = true
            configuration.excludesCurrentProcessAudio = true
            configuration.sampleRate = Int(sampleRate)
            configuration.channelCount = 1
            configuration.width = 2
            configuration.height = 2
            configuration.queueDepth = 1
            configuration.showsCursor = false
            configuration.minimumFrameInterval = CMTime(value: 1, timescale: 1)

            let output = AudioStreamOutput(sampleRate: sampleRate)
            let queue = DispatchQueue(label: "com.realtimesubtitle.system-audio.samples")
            let stream = SCStream(filter: filter, configuration: configuration, delegate: output)
            try stream.addStreamOutput(output, type: .audio, sampleHandlerQueue: queue)
            try await stream.startCapture()

            FileHandle.standardError.write(Data("READY\n".utf8))
            // The Python parent terminates this helper when capture stops.
            // Sleeping asynchronously keeps ScreenCaptureKit callbacks alive
            // without creating or activating a user-facing window.
            while true {
                try await Task.sleep(nanoseconds: 60_000_000_000)
            }
        } catch {
            FileHandle.standardError.write(
                Data("System audio permission or capture error: \(error.localizedDescription)\n".utf8)
            )
            exit(3)
        }
    }
}
