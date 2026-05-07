// PDFExporter.swift
// BizSimAI
//
// Generates PDF reports of simulation results for sharing with professors.
// Uses UIGraphicsPDFRenderer for native iOS PDF generation.

import SwiftUI
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
    private let lineHeight: CGFloat = 20
    
    func generate() -> URL? {
        let fileURL = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("BizSimAI_Results_\(session.sessionCode).pdf")
        
        let renderer = UIGraphicsPDFRenderer(bounds: CGRect(x: 0, y: 0, width: pageWidth, height: pageHeight))
        
        let data = renderer.pdfData { context in
            var mutableY = pageHeight - margin
            
            // Title
            let title = "BizSimAI — Simulation Results"
            let titleAttrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.boldSystemFont(ofSize: 22),
                .foregroundColor: UIColor.systemBlue
            ]
            let titleRect = CGRect(x: margin, y: mutableY, width: pageWidth - 2 * margin, height: lineHeight * 2)
            title.draw(in: titleRect, withAttributes: titleAttrs)
            mutableY -= lineHeight * 3
            
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
                let rect = CGRect(x: margin, y: mutableY, width: pageWidth - 2 * margin, height: lineHeight)
                line.draw(in: rect, withAttributes: [.font: font])
                mutableY -= lineHeight
            }
            mutableY -= 10
            
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
            let spendingHeader = "Cumulative Investments"
            let spendingRect = CGRect(x: margin, y: mutableY, width: pageWidth - 2 * margin, height: lineHeight)
            spendingHeader.draw(in: spendingRect, withAttributes: headerAttrs)
            mutableY -= lineHeight + 5
            
            for (label, value) in spendingLines {
                let labelRect = CGRect(x: margin, y: mutableY, width: 200, height: lineHeight)
                label.draw(in: labelRect, withAttributes: [.font: UIFont.systemFont(ofSize: 10)])
                let valueRect = CGRect(x: pageWidth - margin - 120, y: mutableY, width: 120, height: lineHeight)
                value.draw(in: valueRect, withAttributes: [.font: UIFont.monospacedDigitSystemFont(ofSize: 10, weight: .regular), .foregroundColor: UIColor.systemGreen])
                mutableY -= lineHeight
            }
            mutableY -= 10
            
            // Round table
            let roundHeader = "Round-by-Round Results"
            let roundHeaderRect = CGRect(x: margin, y: mutableY, width: pageWidth - 2 * margin, height: lineHeight)
            roundHeader.draw(in: roundHeaderRect, withAttributes: headerAttrs)
            mutableY -= lineHeight + 5
            
            let colHeaders = ["Round", "Revenue", "Profit", "Mkt Share", "Price", "S/Q"]
            let colWidths: [CGFloat] = [50, 90, 90, 80, 90, 60]
            var x = margin
            let colFont = UIFont.boldSystemFont(ofSize: 9)
            
            for (i, col) in colHeaders.enumerated() {
                let rect = CGRect(x: x, y: mutableY, width: colWidths[i], height: lineHeight)
                col.draw(in: rect, withAttributes: [.font: colFont, .foregroundColor: UIColor.white, .backgroundColor: UIColor.systemGray5])
                x += colWidths[i]
            }
            mutableY -= lineHeight + 3
            
            let rowFont = UIFont.monospacedDigitSystemFont(ofSize: 9, weight: .regular)
            for (roundIdx, round) in rounds.enumerated() {
                x = margin
                let bgColor = roundIdx % 2 == 0 ? UIColor.systemGray6 : UIColor.clear
                let bgRect = CGRect(x: margin, y: mutableY, width: pageWidth - 2 * margin, height: lineHeight)
                bgColor.setFill()
                UIGraphicsGetCurrentContext()?.fill(bgRect)
                
                let values: [String] = [
                    "\(round.roundNumber)",
                    formatted(round.revenue),
                    formatted(round.profit),
                    String(format: "%.1f%%", round.marketShare * 100),
                    String(format: "$%.2f", round.price),
                    String(format: "%.1f", playerTeam.sqRating)
                ]
                
                for (i, value) in values.enumerated() {
                    let rect = CGRect(x: x, y: mutableY, width: colWidths[i], height: lineHeight)
                    value.draw(in: rect, withAttributes: [.font: rowFont, .foregroundColor: UIColor.darkGray])
                    x += colWidths[i]
                }
                mutableY -= lineHeight
                
                if mutableY < margin + lineHeight * 2 {
                    break
                }
            }
            
            // Footer
            let footer = "Generated by BizSimAI • \(Date().formatted(date: .numeric, time: .standard))"
            let footerAttrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: 8),
                .foregroundColor: UIColor.systemGray
            ]
            let footerRect = CGRect(x: margin, y: mutableY, width: pageWidth - 2 * margin, height: lineHeight)
            footer.draw(in: footerRect, withAttributes: footerAttrs)
        }
        
        do {
            try data.write(to: fileURL)
            return fileURL
        } catch {
            print("PDF export failed: \(error)")
            return nil
        }
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
