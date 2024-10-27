# Remootio v3 Integration for Home Assistant

This is a Home Assistant integration for Remootio v3 garage door and gate opener devices.

## Prerequisites

To use this integration with your Remootio device:

1. The device must be connected to your Wi-Fi
2. A fixed IP address must be assigned
3. A status sensor must be installed
4. API access must be enabled on the device

## Setup Instructions

1. Enable API access on your Remootio device:
   - Access the device using the master key via the Remootio app
   - Go to the _Websocket API_ settings in the _Device software_ section
   - Enable the API with logging
   - Note down the IP address and API credentials shown in the app

2. Install the integration:
   - Add this repository to HACS as a custom repository
   - Install the integration through HACS
   - Restart Home Assistant
   - Add the integration through the Home Assistant UI

3. Configure the integration:
   - Enter the IP address (or hostname) of your Remootio device
   - Enter the API Secret Key and API Auth Key from the Remootio app
   - Select the device class (garage door or gate)

## Features

- Open/Close control
- Real-time state updates
- Status sensor support
- Left open notifications

## Support

For issues and feature requests, please use the [GitHub issue tracker](https://github.com/peaceduck/remootio/issues).