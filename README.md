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

Enter your Dwelo account email and password. The integration will log in, auto-discover your units, and prompt you to select one if you have multiple.

If your session token expires, the integration will automatically re-authenticate using your stored credentials. If that fails (e.g. password changed), you'll be prompted to re-enter your credentials via the Home Assistant UI.

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
