import Foundation
import NaturalLanguage
import Translation

private struct TranslationError: Error, CustomStringConvertible {
    let description: String
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

@main
enum MacTranslationCLI {
    static func main() async {
        do {
            guard #available(macOS 26.0, *) else {
                throw TranslationError(description: "Apple Translation in Realtime Subtitle requires macOS 26 or later")
            }
            let arguments = CommandLine.arguments
            guard arguments.count == 4 else {
                throw TranslationError(description: "Usage: mac-translation <source|auto> <target> <text>")
            }

            let text = arguments[3].trimmingCharacters(in: .whitespacesAndNewlines)
            guard !text.isEmpty else {
                print("")
                return
            }

            let sourceIdentifier = try languageIdentifier(for: text, requested: arguments[1])
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
