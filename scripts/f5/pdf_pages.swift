// Rasterize every page of a PDF to PNG with PDFKit (macOS), for blinded reader kits.
// Usage: swift scripts/f5/pdf_pages.swift INPUT.pdf OUTPUT_DIR [scale]
import AppKit
import PDFKit

let args = CommandLine.arguments
guard args.count >= 3, let doc = PDFDocument(url: URL(fileURLWithPath: args[1])) else {
    FileHandle.standardError.write("usage: pdf_pages.swift INPUT.pdf OUTPUT_DIR [scale]\n".data(using: .utf8)!)
    exit(2)
}
let scale = args.count > 3 ? CGFloat(Double(args[3]) ?? 2) : 2
let out = URL(fileURLWithPath: args[2])
try FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)
for index in 0..<doc.pageCount {
    guard let page = doc.page(at: index) else { continue }
    let bounds = page.bounds(for: .mediaBox)
    let size = NSSize(width: bounds.width * scale, height: bounds.height * scale)
    let image = NSImage(size: size)
    image.lockFocus()
    NSColor.white.set()
    NSRect(origin: .zero, size: size).fill()
    let context = NSGraphicsContext.current!.cgContext
    context.scaleBy(x: scale, y: scale)
    page.draw(with: .mediaBox, to: context)
    image.unlockFocus()
    guard let tiff = image.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff),
          let png = rep.representation(using: .png, properties: [:]) else { exit(1) }
    try png.write(to: out.appendingPathComponent(String(format: "page-%02d.png", index + 1)))
}
print(doc.pageCount)
