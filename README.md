# Dwelo Integration for Home Assistant

A custom [Home Assistant](https://www.home-assistant.io/) integration for [Dwelo](https://www.dwelo.com/) smart apartment systems.

## Features

- **Lights** — on/off switches and dimmable lights, auto-discovered from your Dwelo gateway
- **Community door buzzers** — press-button entities for community perimeter doors

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations** → **⋮** → **Custom repositories**
3. Add `mzenko/ha-dwelo` as an **Integration**
4. Search for "Dwelo" and install it
5. Restart Home Assistant

### Manual

Copy `custom_components/dwelo/` to your Home Assistant `custom_components/` directory and restart.

## Configuration

Add the integration via **Settings** → **Devices & Services** → **Add Integration** → **Dwelo**.

You'll need a Dwelo API token:

1. Open Chrome DevTools (F12) → **Network** tab
2. Sign in to [web.dwelo.com](https://web.dwelo.com)
3. Find any request to `api.dwelo.com`
4. Copy the token value from the `Authorization: Token <token>` header

The integration will auto-discover your units. If you have multiple units, you'll be prompted to select one.

## Supported Devices

| Platform | Device Type | Features |
|----------|-------------|----------|
| Light | Binary switch | On/off |
| Light | Dimmer (multilevel switch) | On/off, brightness |
| Button | Community perimeter door | Press to buzz open |

## Development

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env  # fill in your credentials
uv run pytest tests/
```
