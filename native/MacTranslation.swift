import Foundation
import NaturalLanguage
import Translation

private struct TranslationError: Error, CustomStringConvertible {
    let description: String
}

private struct ServerRequest: Decodable {
    let id: Int
    let text: String
}

private struct ServerResponse: Encodable {
    let id: Int
    let translated: String?
    let error: String?
}

private func writeResponse(_ response: ServerResponse) {
    do {
        var data = try JSONEncoder().encode(response)
        data.append(0x0A)
        FileHandle.standardOutput.write(data)
    } catch {
        FileHandle.standardError.write(Data("Unable to encode response: \(error)\n".utf8))
    }
}

private func languageIdentifier(for text: String, requested: String) throws -> String {
    if !requested.isEmpty && requested.lowercased() != "auto" {
        return requested
    }
    let recognizer = NLLanguageRecognizer()
    recognizer.processString(text)
    guard let language = recognizer.dominantLanguage else {
        throw TranslationError(description: "Unable to detect the source language")
    }
    return language.rawValue
}

@available(macOS 26.0, *)
private func runServer(sourceIdentifier: String, targetIdentifier: String) async throws {
    guard sourceIdentifier.lowercased() != "auto" else {
        throw TranslationError(description: "Persistent translation requires a fixed source language")
    }
    let source = Locale.Language(identifier: sourceIdentifier)
    let target = Locale.Language(identifier: targetIdentifier)
    let availability = LanguageAvailability()
    let status = await availability.status(from: source, to: target)
    guard status == .installed else {
        let label = status == .supported ? "language assets are not installed" : "language pair is unsupported"
        throw TranslationError(description: "Apple Translation \(label): \(sourceIdentifier) → \(targetIdentifier)")
    }

    // Reusing one TranslationSession avoids paying process and framework
    // initialization costs for every partial/final subtitle update.
    let session = TranslationSession(installedSource: source, target: target)
    while let line = readLine(strippingNewline: true) {
        do {
            let request = try JSONDecoder().decode(ServerRequest.self, from: Data(line.utf8))
            let text = request.text.trimmingCharacters(in: .whitespacesAndNewlines)
            if text.isEmpty {
                writeResponse(ServerResponse(id: request.id, translated: "", error: nil))
                continue
            }
            let response = try await session.translate(text)
            writeResponse(ServerResponse(id: request.id, translated: response.targetText, error: nil))
        } catch {
            let requestID = (try? JSONDecoder().decode(ServerRequest.self, from: Data(line.utf8)).id) ?? -1
            writeResponse(ServerResponse(id: requestID, translated: nil, error: "\(error)"))
        }
    }
}

@main
enum MacTranslationCLI {
    static func main() async {
        do {
            guard #available(macOS 26.0, *) else {
                throw TranslationError(description: "Apple Translation in Realtime Subtitle requires macOS 26 or later")
            }
            let arguments = CommandLine.arguments
            if arguments.count == 4 && arguments[1] == "--server" {
                try await runServer(
                    sourceIdentifier: arguments[2],
                    targetIdentifier: arguments[3]
                )
                return
            }
            guard arguments.count == 4 else {
                throw TranslationError(description: "Usage: mac-translation <source|auto> <target> <text>")
            }

            let text = arguments[3].trimmingCharacters(in: .whitespacesAndNewlines)
            guard !text.isEmpty else {
                print("")
                return
            }

            let sourceIdentifier = try languageIdentifier(for: text, requested: arguments[1])
            if sourceIdentifier.lowercased() == arguments[2].lowercased() {
                print(text)
                return
            }
            let source = Locale.Language(identifier: sourceIdentifier)
            let target = Locale.Language(identifier: arguments[2])
            let availability = LanguageAvailability()
            let status = await availability.status(from: source, to: target)
            guard status == .installed else {
                let label = status == .supported ? "language assets are not installed" : "language pair is unsupported"
                throw TranslationError(description: "Apple Translation \(label): \(sourceIdentifier) → \(arguments[2])")
            }

            let session = TranslationSession(installedSource: source, target: target)
            let response = try await session.translate(text)
            print(response.targetText)
        } catch {
            FileHandle.standardError.write(Data("\(error)\n".utf8))
            Foundation.exit(1)
        }
    }
}
