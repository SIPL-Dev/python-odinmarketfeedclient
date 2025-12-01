# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-11-26

### Added
- Initial release of ODIN Market Feed SDK
- WebSocket client for ODIN Market Feed API
- Support for LTP (Last Traded Price) touchline subscriptions
- Support for market depth (best five) subscriptions
- Pause/Resume functionality for subscriptions
- Binary market data parsing
- ZLIB compression and decompression support
- Message fragmentation and defragmentation handling
- Async/await API for modern Python applications
- Comprehensive documentation and examples
- Event handlers for open, message, error, and close events

### Features
- `ODINMarketFeedClient` main client class
- `subscribe_ltp_touchline()` method
- `unsubscribe_ltp_touchline()` method
- `subscribe_touchline()` method with custom options
- `unsubscribe_touchline()` method
- `subscribe_best_five()` method
- `unsubscribe_best_five()` method
- `subscribe_pause_resume()` method


## Version History Summary

- **1.0.0** (2024-11-26): Initial release with core functionality
