// macOS-only optional OCR utility. Runtime on Render does not use this file.
import Foundation
import Vision
import AppKit

var output: [[String: Any]] = []
for path in CommandLine.arguments.dropFirst() {
    do {
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.recognitionLanguages = ["ko-KR", "en-US"]
        request.usesLanguageCorrection = true
        let handler = VNImageRequestHandler(url: URL(fileURLWithPath: path), options: [:])
        try handler.perform([request])
        let lines = (request.results ?? []).compactMap { $0.topCandidates(1).first }
        output.append(["path": path, "text": lines.map { $0.string }.joined(separator: "\n"),
                       "confidence": lines.isEmpty ? 0 : lines.map { Double($0.confidence) }.reduce(0, +) / Double(lines.count)])
    } catch {
        output.append(["path": path, "text": "", "error": String(describing: error)])
    }
}
let data = try JSONSerialization.data(withJSONObject: output, options: [.sortedKeys])
print(String(data: data, encoding: .utf8)!)
