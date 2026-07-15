// PDFExporter.swift
// BizSimAI
//
// Generates PDF reports of simulation results for sharing with professors.
// Uses UIGraphicsPDFRenderer for native iOS PDF generation.
// Supports multi-page output with automatic page breaks.

import SwiftUI
import os
import UIKit

// MARK: - PDF Exporter

class PDFExporter {
    
    static func exportSessionResult(session: SimulationSession, playerTeam: TeamStatus, allRounds: [RoundSummary]) -> URL? {
        let renderer = PDFRenderer(session: session, playerTeam: playerTeam, rounds: allRounds)
        return renderer.generate()
    }
}

// MARK: - PDF Renderer

private struct PDFRenderer {
    let session: SimulationSession
    let playerTeam: TeamStatus
    let rounds: [RoundSummary]
    
    private let pageWidth: CGFloat = 612
    private let pageHeight: CGFloat = 792
    private let margin: CGFloat = 50
    private let lineHeight: CGFloat = 18
    
    /// Generate the PDF, handling multi-page layout.
    func generate() -> URL? {
        let fileURL = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("BizSimAI_Results_\(session.sessionCode).pdf")
        
        let bounds = CGRect(x: 0, y: 0, width: pageWidth, height: pageHeight)
        let renderer = UIGraphicsPDFRenderer(bounds: bounds)
        
        let data = renderer.pdfData { context in
            var y: CGFloat = margin
            
            context.beginPage()
            
            // Title
            let title = "BizSimAI — Simulation Results"
            let titleAttrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.boldSystemFont(ofSize: 22),
                .foregroundColor: UIColor.systemBlue
            ]
            title.draw(at: CGPoint(x: margin, y: y), withAttributes: titleAttrs)
            y += lineHeight * 2.5
            
            // Session info
            let infoLines: [String] = [
                "Session Code: \(session.sessionCode)",
                "Team: \(playerTeam.name)",
                "Round: \(session.currentRound) / \(session.totalRounds)",
                "Equity: \(formatted(playerTeam.equity))",
                "Cash: \(formatted(playerTeam.cash))",
                "Total Debt: \(formatted(playerTeam.totalDebt))",
                "Shares Outstanding: \(playerTeam.sharesOutstanding)",
                "S/Q Rating: \(String(format: "%.1f", playerTeam.sqRating))",
                "Image Rating: \(String(format: "%.0f", playerTeam.imageRating))",
                "Credit Rating: \(playerTeam.creditRating.rawValue)",
                "Investor Score: \(String(format: "%.1f", playerTeam.cumulativeInvestorScore))"
            ]
            
            let font = UIFont.systemFont(ofSize: 11)
            for line in infoLines {
                y = ensureSpace(y: &y, needed: lineHeight, context: context)
                line.draw(at: CGPoint(x: margin, y: y), withAttributes: [.font: font])
                y += lineHeight
            }
            y += 8
            
            // Cumulative spending
            let spendingLines: [(String, String)] = [
                ("Cumulative R&D", formatted(playerTeam.cumulativeRD)),
                ("Cumulative Marketing", formatted(playerTeam.cumulativeMarketing)),
                ("Cumulative CSR", formatted(playerTeam.cumulativeCSR)),
                ("Cumulative TQM", formatted(playerTeam.cumulativeTQM))
            ]
            
            let headerAttrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.boldSystemFont(ofSize: 14),
                .foregroundColor: UIColor.darkGray
            ]
            y = ensureSpace(y: &y, needed: lineHeight * 2, context: context)
            "Cumulative Investments".draw(at: CGPoint(x: margin, y: y), withAttributes: headerAttrs)
            y += lineHeight + 4
            
            for (label, value) in spendingLines {
                y = ensureSpace(y: &y, needed: lineHeight, context: context)
                label.draw(at: CGPoint(x: margin, y: y), withAttributes: [.font: UIFont.systemFont(ofSize: 10)])
                value.draw(at: CGPoint(x: pageWidth - margin - 120, y: y), withAttributes: [
                    .font: UIFont.monospacedDigitSystemFont(ofSize: 10, weight: .regular),
                    .foregroundColor: UIColor.systemGreen
                ])
                y += lineHeight
            }
            y += 8
            
            // Round table
            y = ensureSpace(y: &y, needed: lineHeight * 3, context: context)
            "Round-by-Round Results".draw(at: CGPoint(x: margin, y: y), withAttributes: headerAttrs)
            y += lineHeight + 4
            
            let colHeaders = ["Round", "Revenue", "Profit", "Mkt Share", "Price", "S/Q"]
            let colWidths: [CGFloat] = [50, 90, 90, 80, 90, 60]
            let colFont = UIFont.boldSystemFont(ofSize: 9)
            
            // Draw header row background
            let headerBgRect = CGRect(x: margin, y: y, width: pageWidth - 2 * margin, height: lineHeight)
            UIColor.systemGray5.setFill()
            UIGraphicsGetCurrentContext()?.fill(headerBgRect)
            
            var x = margin
            for (i, col) in colHeaders.enumerated() {
                col.draw(at: CGPoint(x: x, y: y + 2), withAttributes: [.font: colFont, .foregroundColor: UIColor.white])
                x += colWidths[i]
            }
            y += lineHeight + 2
            
            let rowFont = UIFont.monospacedDigitSystemFont(ofSize: 9, weight: .regular)
            for (roundIdx, round) in rounds.enumerated() {
                y = ensureSpace(y: &y, needed: lineHeight, context: context)
                
                // Alternating row background
                if roundIdx % 2 == 0 {
                    let bgRect = CGRect(x: margin, y: y, width: pageWidth - 2 * margin, height: lineHeight)
                    UIColor.systemGray6.setFill()
                    UIGraphicsGetCurrentContext()?.fill(bgRect)
                }
                
                x = margin
                let values: [String] = [
                    "\(round.roundNumber)",
                    formatted(round.revenue),
                    formatted(round.profit),
                    String(format: "%.1f%%", round.marketShare * 100),
                    String(format: "$%.2f", round.price),
                    String(format: "%.1f", playerTeam.sqRating)
                ]
                
                for (i, value) in values.enumerated() {
                    value.draw(at: CGPoint(x: x, y: y + 2), withAttributes: [.font: rowFont, .foregroundColor: UIColor.darkGray])
                    x += colWidths[i]
                }
                y += lineHeight
            }
            
            // Footer
            y = ensureSpace(y: &y, needed: lineHeight, context: context)
            let footer = "Generated by BizSimAI • \(Date().formatted(date: .numeric, time: .standard))"
            footer.draw(at: CGPoint(x: margin, y: y), withAttributes: [
                .font: UIFont.systemFont(ofSize: 8),
                .foregroundColor: UIColor.systemGray
            ])
        }
        
        do {
            try data.write(to: fileURL)
            Logger.pdf.info("PDF exported to \(fileURL.lastPathComponent)")
            return fileURL
        } catch {
            Logger.pdf.error("PDF export failed: \(UserFriendlyError.message(for: error))")
            return nil
        }
    }
    
    /// Ensure there is enough vertical space; if not, start a new page.
    @discardableResult
    private func ensureSpace(y: inout CGFloat, needed: CGFloat, context: UIGraphicsPDFRendererContext) -> CGFloat {
        if y + needed > pageHeight - margin {
            context.beginPage()
            y = margin
        }
        return y
    }
    
    private func formatted(_ value: Double) -> String {
        if value >= 1_000_000 {
            return String(format: "$%.1fM", value / 1_000_000)
        } else if value >= 1_000 {
            return String(format: "$%.1fK", value / 1_000)
        }
        return String(format: "$%.0f", value)
    }
}
