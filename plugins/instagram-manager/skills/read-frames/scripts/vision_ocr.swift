// The words macOS's own text reader (Apple Vision) finds on each image, one JSON line per image:
//   {"file": "<path>", "text": "<line>\n<line>..."}
// Vision reads styled subtitles (outlined, yellow, bold over a busy picture) that tesseract misses.
// Usage: swift vision_ocr.swift <image> [<image> ...]   (or compile once with swiftc for speed)
import Foundation
import Vision

func read(_ path: String) -> String {
    let url = URL(fileURLWithPath: path)
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false  // names, handles and street numbers are not dictionary words
    let handler = VNImageRequestHandler(url: url, options: [:])
    do {
        try handler.perform([request])
    } catch {
        return ""
    }
    let lines = (request.results ?? []).compactMap { $0.topCandidates(1).first?.string }
    return lines.joined(separator: "\n")
}

for path in CommandLine.arguments.dropFirst() {
    let line: [String: String] = ["file": path, "text": read(path)]
    if let data = try? JSONSerialization.data(withJSONObject: line),
       let s = String(data: data, encoding: .utf8) {
        print(s)
    }
}
