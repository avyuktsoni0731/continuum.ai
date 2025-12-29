#!/bin/bash

# Manage both continuum.ai services (MCP Server and Slack Bot)

case "$1" in
    start)
        echo "🚀 Starting continuum.ai services..."
        sudo systemctl start continuum-mcp
        sudo systemctl start continuum-slack-bot
        echo "✅ Services started!"
        echo ""
        echo "MCP Server: http://$(curl -s ifconfig.me):8000/mcp/"
        echo "Slack Bot: http://$(curl -s ifconfig.me):3000/health"
        ;;
    stop)
        echo "🛑 Stopping continuum.ai services..."
        sudo systemctl stop continuum-mcp
        sudo systemctl stop continuum-slack-bot
        echo "✅ Services stopped!"
        ;;
    restart)
        echo "🔄 Restarting continuum.ai services..."
        sudo systemctl restart continuum-mcp
        sudo systemctl restart continuum-slack-bot
        echo "✅ Services restarted!"
        ;;
    status)
        echo "📊 === MCP Server Status ==="
        sudo systemctl status continuum-mcp --no-pager -l
        echo ""
        echo "📊 === Slack Bot Status ==="
        sudo systemctl status continuum-slack-bot --no-pager -l
        ;;
    logs)
        echo "📋 Showing logs (Ctrl+C to exit)..."
        sudo journalctl -u continuum-mcp -u continuum-slack-bot -f
        ;;
    logs-mcp)
        echo "📋 MCP Server logs (Ctrl+C to exit)..."
        sudo journalctl -u continuum-mcp -f
        ;;
    logs-slack)
        echo "📋 Slack Bot logs (Ctrl+C to exit)..."
        sudo journalctl -u continuum-slack-bot -f
        ;;
    enable)
        echo "🔧 Enabling services to start on boot..."
        sudo systemctl enable continuum-mcp
        sudo systemctl enable continuum-slack-bot
        echo "✅ Services enabled!"
        ;;
    disable)
        echo "🔧 Disabling services from starting on boot..."
        sudo systemctl disable continuum-mcp
        sudo systemctl disable continuum-slack-bot
        echo "✅ Services disabled!"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|logs-mcp|logs-slack|enable|disable}"
        echo ""
        echo "Commands:"
        echo "  start       - Start both services"
        echo "  stop        - Stop both services"
        echo "  restart     - Restart both services"
        echo "  status      - Show status of both services"
        echo "  logs        - Show logs from both services (follow mode)"
        echo "  logs-mcp    - Show MCP server logs only"
        echo "  logs-slack  - Show Slack bot logs only"
        echo "  enable      - Enable services to start on boot"
        echo "  disable     - Disable services from starting on boot"
        exit 1
        ;;
esac

