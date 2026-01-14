#!/bin/bash
# Setup Cron Jobs for Investor-Agent Prediction Tracking
# Run this script once to install the cron jobs

echo "================================================"
echo "Setting up Investor-Agent Cron Jobs"
echo "================================================"

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOG_DIR="/var/log/investor-agent"

# Create log directory
echo "Creating log directory..."
sudo mkdir -p $LOG_DIR
sudo chown $(whoami) $LOG_DIR

# Create the cron job entries
CRON_DAILY="30 16 * * 1-5 docker exec investor-agent-mcp python -m investor_agent.cron_update_predictions >> $LOG_DIR/prediction_updates.log 2>&1"
CRON_WEEKLY="0 18 * * 0 docker exec investor-agent-mcp python -m investor_agent.cron_weekly_report >> $LOG_DIR/efficiency_reports.log 2>&1"

# Check if cron jobs already exist
EXISTING_CRON=$(crontab -l 2>/dev/null || echo "")

if echo "$EXISTING_CRON" | grep -q "cron_update_predictions"; then
    echo "Daily update cron job already exists. Skipping..."
else
    echo "Adding daily prediction update cron job (4:30 PM ET, Mon-Fri)..."
    (echo "$EXISTING_CRON"; echo "$CRON_DAILY") | crontab -
    EXISTING_CRON=$(crontab -l)
fi

if echo "$EXISTING_CRON" | grep -q "cron_weekly_report"; then
    echo "Weekly report cron job already exists. Skipping..."
else
    echo "Adding weekly efficiency report cron job (6:00 PM ET, Sunday)..."
    (echo "$EXISTING_CRON"; echo "$CRON_WEEKLY") | crontab -
fi

echo ""
echo "================================================"
echo "Cron Jobs Installed Successfully!"
echo "================================================"
echo ""
echo "Current cron jobs:"
crontab -l
echo ""
echo "Log files will be written to:"
echo "  - $LOG_DIR/prediction_updates.log (daily)"
echo "  - $LOG_DIR/efficiency_reports.log (weekly)"
echo ""
echo "To test manually:"
echo "  docker exec investor-agent-mcp python -m investor_agent.cron_update_predictions"
echo "  docker exec investor-agent-mcp python -m investor_agent.cron_weekly_report"
echo ""
echo "To remove cron jobs:"
echo "  crontab -e  (then delete the investor-agent lines)"
echo ""
