Read CLAUDE.md and config.json. Execute the FULL build sequence without stopping:

1. Run setup.sh to create directories and install deps
2. Copy/organize any data files from inputs/ into correct subdirectories
3. Build scripts/parsers/sellersprite.py and scripts/parsers/seller_central.py
4. Build scripts/processors/keywords.py, competitors.py, gap_analysis.py, pricing.py, ads.py, traffic.py
5. Build scripts/exporters/excel_writer.py and json_writer.py
6. Build scripts/generate_report.py (main orchestrator)
7. Run: python3 scripts/generate_report.py — verify it produces outputs/COLD_POSH_运营方案_*.xlsx + outputs/run_summary.md
8. Build dashboard/package.json, dashboard/next.config.js, dashboard/app/layout.jsx, dashboard/app/page.jsx, dashboard/app/data.js
9. cd dashboard && npm install && npm run build — verify production build succeeds
10. Report completion status

Do NOT stop to ask questions. Do NOT ask for confirmation between steps. Build everything, run everything, fix errors inline, keep going until all 10 steps are done. $ARGUMENTS
