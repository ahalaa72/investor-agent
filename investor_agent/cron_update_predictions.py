#!/usr/bin/env python3
"""
Cron Job Script: Update Prediction Outcomes
Run daily to track WIN/LOSS status of all open predictions.

Usage:
    # Direct run
    python -m investor_agent.cron_update_predictions

    # Via Docker
    docker exec investor-agent-mcp python -m investor_agent.cron_update_predictions

Cron Setup (run at 4:30 PM ET daily - after market close):
    30 16 * * 1-5 docker exec investor-agent-mcp python -m investor_agent.cron_update_predictions >> /var/log/prediction_updates.log 2>&1
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
    """Run prediction outcome update."""
    logger.info("=" * 60)
    logger.info(f"PREDICTION UPDATE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    try:
        from investor_agent.prediction_tracker import PredictionTracker

        tracker = PredictionTracker()
        result = tracker.update_outcomes()

        # Log results
        logger.info(f"Status: {result.get('status')}")
        logger.info(f"Total Open: {result.get('total_open', 0)}")
        logger.info(f"Updated: {result.get('updated', 0)}")
        logger.info(f"Newly Validated: {result.get('newly_validated', 0)}")

        outcomes = result.get('outcomes', {})
        logger.info(f"Outcomes - WIN: {outcomes.get('WIN', 0)}, LOSS: {outcomes.get('LOSS', 0)}, OPEN: {outcomes.get('OPEN', 0)}")

        # Print details for each updated prediction
        for pred in result.get('updated_predictions', []):
            logger.info(
                f"  {pred['ticker']} {pred['direction']}: "
                f"Return {pred.get('return_current', 0):.2f}%, "
                f"Outcome: {pred['outcome']}, "
                f"Days: {pred.get('days_held', 0)}"
            )

        logger.info("=" * 60)
        logger.info("UPDATE COMPLETE")
        logger.info("=" * 60)

        # Return success
        return 0

    except Exception as e:
        logger.error(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
