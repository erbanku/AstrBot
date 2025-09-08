# WhatsApp Platform Integration for AstrBot

This document explains how to set up and use the WhatsApp platform integration in AstrBot.

## Overview

The WhatsApp integration allows AstrBot to send and receive messages through WhatsApp Web using browser automation with Selenium WebDriver. This provides a way to use AstrBot with WhatsApp without requiring complex API setups or business verification.

## Features

- ✅ Send and receive text messages
- ✅ Send and receive images
- ✅ Send and receive files/documents
- ✅ Send and receive audio messages
- ✅ Group chat support
- ✅ QR code authentication
- ✅ Automatic reconnection
- ✅ Configurable polling and timeouts

## Prerequisites

1. **Python 3.10+** with AstrBot installed
2. **Chrome or Chromium browser** installed on your system
3. **Selenium dependency** (automatically installed with AstrBot)
4. **WhatsApp account** with access to WhatsApp Web

## Quick Setup

### 1. Add WhatsApp Platform Configuration

Add the following configuration to your AstrBot platform settings:

```json
{
  "type": "whatsapp",
  "enable": true,
  "id": "my_whatsapp_bot",
  "whatsapp_headless": false,
  "whatsapp_timeout": 30,
  "whatsapp_poll_interval": 2,
  "whatsapp_max_retries": 3
}
```

### 2. Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `whatsapp_headless` | boolean | `true` | Run browser in headless mode (no GUI) |
| `whatsapp_timeout` | integer | `30` | Timeout in seconds for browser operations |
| `whatsapp_poll_interval` | integer | `2` | Interval in seconds between message polls |
| `whatsapp_max_retries` | integer | `3` | Maximum reconnection attempts |

## Usage

Once configured, AstrBot will:

1. **Receive messages** from WhatsApp contacts and groups
2. **Process messages** through your configured LLM and plugins
3. **Send responses** back to WhatsApp

### Example Usage

Send a message to any contact that has your WhatsApp bot number, and AstrBot will respond according to your configured persona and plugins.

## Support

For issues and questions:

1. Check the [AstrBot documentation](https://github.com/Soulter/AstrBot)
2. Report bugs on [GitHub Issues](https://github.com/Soulter/AstrBot/issues)
3. Join the community discussions