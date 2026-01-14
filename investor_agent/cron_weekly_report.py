#!/usr/bin/env python3
"""
Cron Job Script: Generate Weekly Efficiency Report
Run weekly to analyze prediction accuracy.

Usage:
    # Direct run
    python -m investor_agent.cron_weekly_report

    # Via Docker
    docker exec investor-agent-mcp python -m investor_agent.cron_weekly_report

Cron Setup (run Sunday at 6 PM):
    0 18 * * 0 docker exec investor-agent-mcp python -m investor_agent.cron_weekly_report >> /var/log/efficiency_reports.log 2>&1
"""

import sys
import json
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Generate weekly efficiency report."""
    logger.info("=" * 60)
    logger.info(f"WEEKLY EFFICIENCY REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    try:
        from investor_agent.prediction_tracker import EfficiencyReportGenerator

        generator = EfficiencyReportGenerator()
        result = generator.generate_weekly_report(period_days=7, min_sample=5)

        # Log results
        logger.info(f"Status: {result.get('status')}")
        logger.info(f"Report Date: {result.get('report_date')}")
        logger.info(f"Period: {result.get('period')}")

        summary = result.get('executive_summary', {})
        logger.info(f"Total Predictions: {summary.get('total_predictions', 0)}")
        logger.info(f"Validated: {summary.get('validated', 0)}")
        logger.info(f"Overall Win Rate: {summary.get('overall_win_rate', 0)}%")
        logger.info(f"Best Component: {summary.get('best_component', 'N/A')}")

        # Print gate accuracy
        gate_accuracy = result.get('gate_accuracy', {})
        logger.info("\nGate Accuracy:")
        for gate, data in gate_accuracy.items():
            logger.info(f"  {gate}: {data.get('accuracy', 0)}%")

        # Print full markdown report
        if result.get('full_report_markdown'):
            logger.info("\n" + "=" * 60)
            logger.info("FULL REPORT:")
            logger.info("=" * 60)
            print(result['full_report_markdown'])

        logger.info("=" * 60)
        logger.info("REPORT COMPLETE")
        logger.info("=" * 60)

        return 0

    except Exception as e:
        logger.error(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
