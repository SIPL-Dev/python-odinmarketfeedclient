# ODIN Market Feed SDK

A Python SDK for connecting to ODIN Market Feed WebSocket API to receive real-time trading and market data.

## Features

- 🚀 Real-time market data streaming via WebSocket
- 📊 Support for touchline and market depth (best five) subscriptions
- 🗜️ Built-in ZLIB compression/decompression
- 🔄 Automatic message fragmentation and defragmentation
- ⏸️ Pause/Resume subscription capability
- 📦 Binary market data parsing
- 🎯 Simple and intuitive async/await API

## Installation

### From PyPI (once published)
```bash
pip install odin-market-feed
```

### From GitHub
```bash
pip install git+https://github.com/python-odinmarketfeedclient.git
```

### From Source
```bash
git clone https://github.com/python-odinmarketfeedclient.git
cd odin-market-feed
pip install -e .
```

## Quick Start

```python
import asyncio
from odin_market_feed import ODINMarketFeedClient

async def main():
    # Create client instance
    client = ODINMarketFeedClient()
    
    # Define event handlers
    async def on_open():
        print("WebSocket connection opened")
        # Subscribe to market data for specific tokens
        await client.subscribe_ltp_touchline(["1_22", "1_2885"])
    
    def on_message(message):
        print(f"Received market data: {message}")
    
    def on_error(error):
        print(f"Error occurred: {error}")
    
    def on_close(code, reason):
        print(f"Connection closed: {code} - {reason}")
    
    # Set event handlers
    client.on_open = on_open
    client.on_message = on_message
    client.on_error = on_error
    client.on_close = on_close
    
    # Connect to the server
    await client.connect(
        host="your.server.com",
        port=4509,
        is_ssl=False,
        user_id="YOUR_USER_ID",
        authentication_key=""
    )
    
    # Keep connection alive
    await asyncio.sleep(60)
    
    # Disconnect
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

## API Reference

### ODINMarketFeedClient

Main client class for connecting to ODIN Market Feed WebSocket API.

#### Methods

##### `connect(host, port, is_ssl, user_id, authentication_key)`
Connect to the WebSocket server.

**Parameters:**
- `host` (str): Server hostname or IP address
- `port` (int): Server port number
- `is_ssl` (bool): Whether to use SSL/TLS
- `user_id` (str): Your user ID
- `authentication_key` (str): Authentication key (if required)

**Returns:** None

##### `disconnect()`
Disconnect from the WebSocket server.

**Returns:** None

##### `subscribe_ltp_touchline(scrip_list)`
Subscribe to Last Traded Price (LTP) touchline data.

**Parameters:**
- `scrip_list` (List[str]): List of scrips in format "segment_token" (e.g., ["1_22", "1_2885"])

**Returns:** None

##### `unsubscribe_ltp_touchline(scrip_list)`
Unsubscribe from LTP touchline data.

**Parameters:**
- `scrip_list` (List[str]): List of scrips to unsubscribe

**Returns:** None

##### `subscribe_touchline(scrip_list)`
Subscribe to touchline data with additional options.

**Parameters:**
- `scrip_list` (List[str]): List of scrips

**Returns:** None

##### `unsubscribe_touchline(scrip_list)`
Unsubscribe from touchline data.

**Parameters:**
- `scrip_list` (List[str]): List of scrips to unsubscribe

**Returns:** None

##### `subscribe_best_five(scrip_list)`
Subscribe to market depth (best five bid/ask) data.

**Parameters:**
- `scrip_list` (List[str]): List of scrips

**Returns:** None

##### `unsubscribe_best_five(scrip_list)`
Unsubscribe from market depth data.

**Parameters:**
- `scrip_list` (List[str]): List of scrips to unsubscribe

**Returns:** None

##### `subscribe_pause_resume(is_pause)`
Pause or resume market data subscription.

**Parameters:**
- `is_pause` (bool): True to pause, False to resume

**Returns:** None


## Requirements

- Python 3.7+
- websockets >= 10.0

## Development

### Setting up development environment

```bash
# Clone the repository
git clone https://github.com/python-odinmarketfeedclient.git
cd odin-market-feed-sdk

# Install in development mode
pip install -e ".[dev]"
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This Library is for educational and development purposes. Please ensure you have the necessary permissions and comply with all relevant regulations when using this SDK for live trading.

## Support

For issues, questions, or contributions, please visit:
- GitHub Issues: https://github.com/python-odinmarketfeedclient/issues
- Documentation: https://github.com/python-odinmarketfeedclient

## Changelog

### Version 1.0.0 (Initial Release)
- WebSocket connectivity with ODIN Market Feed API
- Support for LTP touchline subscriptions
- Support for market depth (best five) subscriptions
- Pause/Resume functionality
- Binary market data parsing
- ZLIB compression support
- Message fragmentation handling
